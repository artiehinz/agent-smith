"""Policy and execution-route telemetry endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import Path
from fastapi.responses import JSONResponse

import core.paths as _paths

from core.policy import (
    ModelAttestation,
    ModelSpec,
    PreflightIntent,
    PreflightResult,
    attestation_payload,
    choose_backend,
    explicit_worker_args,
    generate_preflight_marker,
    get_task_ledger,
    task_events,
    list_open_tasks,
    parse_preflight_output,
    record_task_event,
    run_preflight_probe,
    route_token_budget,
)
from ._common import router

_log = logging.getLogger(__name__)
_POLICY_LEDGER_DB = _paths.REPO_ROOT / ".codex-control" / "policy_task_ledger.sqlite"
_ALLOWED_ROUTES = {"direct", "structured", "parallel"}
_ALLOWED_PREFLIGHT_ROLES = {
    "explorer",
    "executor",
    "tester",
    "reviewer",
    "security review",
    "security_review",
    "security-review",
}


def _normalize_route(raw: Any) -> str | None:
    value = str(raw or "").strip().lower()
    return value if value in _ALLOWED_ROUTES else None


def _normalize_string(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    return value or None


def _normalize_pref_bool(raw: Any, *, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _normalize_preflight_role(raw: Any) -> str | None:
    role = _normalize_string(raw)
    if not role:
        return None
    normalized = role.replace("_", " ").replace("-", " ").strip().lower()
    return normalized if normalized in _ALLOWED_PREFLIGHT_ROLES else None


def _attestation_payload(result: PreflightResult, marker_expected: str | None) -> dict[str, Any]:
    return attestation_payload(result, marker_expected)


def _backend_decision_payload(
    role: str,
    decision,
    route: str | None = None,
    route_hint: str | None = None,
) -> dict[str, Any]:
    return {
        "role": decision.role,
        "selected_backend": decision.selected_backend.value,
        "fallback_backend": decision.fallback_backend.value if decision.fallback_backend else None,
        "fail_closed": decision.fail_closed,
        "requires_approval": decision.requires_approval,
        "route": route,
        "route_hint": route_hint,
        "reason": decision.reason,
    }


def _build_attestation(result: PreflightResult) -> ModelAttestation:
    intended = ModelSpec(name=result.intent.model, effort=result.intent.effort)
    actual = None
    if result.actual_model and result.actual_effort:
        actual = ModelSpec(name=result.actual_model, effort=result.actual_effort)
    return ModelAttestation(role=result.intent.role, intended=intended, actual=actual)


def _coerce_int(raw: Any, default: int = 0) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _normalize_datetime(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _update_policy_field(policy: dict, key: str, value: dict[str, Any]) -> None:
    if not isinstance(policy, dict) or not isinstance(value, dict):
        return

    role = (
        value.get("role")
        or (value.get("intent", {}) or {}).get("role")
    )
    if not isinstance(role, str) or not role.strip():
        return

    current = dict(policy.get(key) or {})
    current[str(role).strip()] = value
    policy[key] = current


def _policy_route_hint(policy: dict[str, Any] | None) -> str | None:
    if not isinstance(policy, dict):
        return None
    route = policy.get("route_hint") or policy.get("route")
    if route:
        return str(route)
    return None


def _coerce_task_limit(raw: Any, *, default: int, minimum: int, maximum: int) -> int:
    value = _coerce_int(raw, default=default)
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


@router.get("/api/policy")
async def api_policy() -> JSONResponse:
    """Return the live session policy blob used for this run."""
    from core import session as scan_session

    scan_session.load_from_disk(force=True)
    session_data = scan_session.get() or {}
    policy = session_data.get("policy")
    if not isinstance(policy, dict):
        return JSONResponse({})
    return JSONResponse(policy)


@router.get("/api/policy/preflight")
async def api_policy_preflight() -> JSONResponse:
    """Return current preflight evidence and backend decisions."""
    from core import session as scan_session

    scan_session.load_from_disk(force=True)
    policy = (scan_session.get() or {}).get("policy")
    if not isinstance(policy, dict):
        return JSONResponse({"ok": True, "preflight": {}, "backend_decisions": {}, "policy_preflight_state": {}})

    return JSONResponse({
        "ok": True,
        "policy_route": _policy_route_hint(policy),
        "preflight": policy.get("preflight", {}),
        "backend_decisions": policy.get("backend_decisions", {}),
        "policy_preflight_state": policy.get("policy_preflight_state", {}),
    })


@router.get("/api/policy/tasks")
async def api_policy_tasks(
    status: str | None = None,
    owner_role: str | None = None,
    route: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    """Return filtered policy tasks for operator review."""
    try:
        filtered = list_open_tasks(
            _POLICY_LEDGER_DB,
            status=status,
            owner_role=owner_role,
            route=route,
            since=_normalize_datetime(since),
            until=_normalize_datetime(until),
            limit=_coerce_task_limit(limit, default=50, minimum=1, maximum=250),
            offset=max(0, _coerce_int(offset, default=0)),
        )
        return JSONResponse({"ok": True, "tasks": filtered, "count": len(filtered)})
    except Exception:
        _log.exception("failed to read policy task list")
        return JSONResponse({"ok": False, "error": "request failed"}, status_code=500)


@router.get("/api/policy/tasks/{task_id}")
async def api_policy_task(task_id: str = Path(pattern=r"[^/]+")) -> JSONResponse:
    """Return one task entry plus its ordered event log."""
    try:
        entry = get_task_ledger(_POLICY_LEDGER_DB, task_id)
        if not entry:
            return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
        events = task_events(_POLICY_LEDGER_DB, task_id)
        return JSONResponse({
            "ok": True,
            "task": entry,
            "events": events,
            "event_count": len(events),
        })
    except Exception:
        _log.exception("failed to read policy task details")
        return JSONResponse({"ok": False, "error": "request failed"}, status_code=500)


@router.post("/api/policy/route")
async def api_set_policy_route(payload: dict | None = None) -> JSONResponse:
    """Apply a route override on the active session policy."""
    route = _normalize_route(payload.get("route") if isinstance(payload, dict) else None)
    if not route:
        return JSONResponse(
            {"ok": False, "error": "invalid route; must be direct|structured|parallel"},
            status_code=400,
        )

    try:
        from core import session as scan_session

        scan_session.load_from_disk(force=True)
        session_data = scan_session.get()
        if not session_data or not isinstance(session_data, dict):
            return JSONResponse({"ok": False, "error": "no active session"}, status_code=409)

        policy = session_data.get("policy")
        if not isinstance(policy, dict):
            budget = route_token_budget(route)
            policy = {
                "route": route,
                "score": 0.0,
                "override_applied": True,
                "rationale": [],
                "details": {
                    "task_breadth": 4,
                    "affected_packages": 0,
                    "uncertainty": 3,
                    "verification_complexity": 5,
                    "independent_work_opportunities": 1,
                    "estimated_agent_overhead": 1,
                },
                "token_budget": budget.__dict__,
                "policy_engine": "route_classifier_v1",
            }
            session_data["policy"] = policy

        policy["route"] = route
        policy["route_hint"] = route
        policy["override_applied"] = True
        policy.setdefault("repair_loop", {}).update({
            "cycle": 0,
            "max_cycles": policy.get("repair_loop", {}).get("max_cycles", 2),
        })
        scan_session._flush()

        task_id = policy.get("ledger_id")
        if isinstance(task_id, str) and task_id:
            try:
                record_task_event(
                    _POLICY_LEDGER_DB,
                    task_id=task_id,
                    kind="route_override",
                    payload={"route": route, "source": "dashboard"},
                )
            except Exception:
                _log.exception("failed to record policy route override event")
        return JSONResponse({"ok": True, "route": route, "policy": policy})
    except Exception:
        _log.exception("failed to set policy route")
        return JSONResponse({"ok": False, "error": "request failed"}, status_code=500)


@router.post("/api/policy/repair")
async def api_set_policy_repair(payload: dict | None = None) -> JSONResponse:
    """Update in-session repair-loop telemetry settings."""
    payload = payload or {}
    cycle = payload.get("cycle")
    max_cycles = payload.get("max_cycles")
    if cycle is None and max_cycles is None:
        return JSONResponse({
            "ok": False,
            "error": "at least one of cycle or max_cycles is required",
        }, status_code=400)

    try:
        from core import session as scan_session

        scan_session.load_from_disk(force=True)
        session_data = scan_session.get() or {}
        policy = session_data.get("policy")
        if not isinstance(policy, dict):
            return JSONResponse({"ok": False, "error": "no active policy"}, status_code=409)

        repair = policy.setdefault("repair_loop", {})
        if cycle is not None:
            repair["cycle"] = _coerce_int(cycle, default=repair.get("cycle", 0))
        if max_cycles is not None:
            repair["max_cycles"] = _coerce_task_limit(max_cycles, default=repair.get("max_cycles", 2), minimum=1, maximum=20)
        policy["repair_loop"] = repair
        scan_session._flush()

        task_id = policy.get("ledger_id")
        if isinstance(task_id, str) and task_id:
            try:
                record_task_event(
                    _POLICY_LEDGER_DB,
                    task_id=task_id,
                    kind="repair_update",
                    payload=dict(repair),
                )
            except Exception:
                _log.exception("failed to record repair-loop update event")
        return JSONResponse({"ok": True, "repair_loop": repair})
    except Exception:
        _log.exception("failed to update policy repair loop")
        return JSONResponse({"ok": False, "error": "request failed"}, status_code=500)


@router.post("/api/policy/preflight")
async def api_run_policy_preflight(payload: dict | None = None) -> JSONResponse:
    """Run or record a policy preflight attestation for one role."""
    payload = payload or {}
    role = _normalize_preflight_role(payload.get("role"))
    if not role:
        return JSONResponse({
            "ok": False,
            "error": "invalid role; must be explorer|executor|tester|reviewer|security review",
        }, status_code=400)

    intended_model = _normalize_string(payload.get("model") or payload.get("intended_model"))
    intended_effort = _normalize_string(payload.get("effort") or payload.get("intended_effort"))
    if not intended_model or not intended_effort:
        return JSONResponse({"ok": False, "error": "model and effort are required"}, status_code=400)

    marker = _normalize_string(payload.get("marker")) or generate_preflight_marker()
    role_sandbox = _normalize_string(payload.get("sandbox")) or "read_only"
    explicit_worker_available = not _normalize_pref_bool(payload.get("prefer_native"), default=False)
    if "explicit_worker_available" in payload:
        explicit_worker_available = _normalize_pref_bool(payload.get("explicit_worker_available"), default=True)
    intent = PreflightIntent(role=role, model=intended_model, effort=intended_effort, sandbox=role_sandbox)
    raw_output = _normalize_string(payload.get("raw_output"))
    mode = "auto"

    try:
        from core import session as scan_session

        if raw_output:
            mode = "manual"
            manual_marker = _normalize_string(payload.get("marker")) or ""
            result = parse_preflight_output(intent, raw_output, manual_marker)
            marker = manual_marker
        else:
            if not marker:
                marker = generate_preflight_marker()
            result = run_preflight_probe(intent, marker)
        marker = result.marker

        attestation = _build_attestation(result)
        decision = choose_backend(
            role=role,
            intended_model=intended_model,
            intended_effort=intended_effort,
            attestation=attestation,
            explicit_worker_available=explicit_worker_available,
        )

        preflight_payload = _attestation_payload(result, marker)
        route = None
        route_hint = None
        decision_payload = _backend_decision_payload(role, decision, route=route, route_hint=route_hint)
        decision_payload["intent"] = {
            "role": role,
            "model": intended_model,
            "effort": intended_effort,
            "sandbox": intent.sandbox,
        }
        decision_payload["command"] = (
            explicit_worker_args(model=intended_model, effort=intended_effort)
            if decision.selected_backend.value == "explicit_codex_exec"
            else None
        )
        decision_payload["mode"] = mode
        preflight_payload["role"] = role
        preflight_payload["mode"] = mode
        preflight_payload["status"] = result.status

        scan_session.load_from_disk(force=True)
        session_data = scan_session.get() or {}
        if not isinstance(session_data, dict):
            return JSONResponse({"ok": False, "error": "no active session"}, status_code=409)

        policy = session_data.get("policy")
        if isinstance(policy, dict):
            route = str(policy.get("route") or "direct")
            raw_route_hint = policy.get("route_hint")
            if raw_route_hint is not None:
                route_hint = str(raw_route_hint)
            decision_payload = _backend_decision_payload(
                role,
                decision,
                route=route,
                route_hint=route_hint,
            )
            if decision.selected_backend.value == "explicit_codex_exec":
                decision_payload["command"] = explicit_worker_args(model=intended_model, effort=intended_effort)
            else:
                decision_payload["command"] = None
        repair_payload = {"cycle": 0, "max_cycles": 2}
        if isinstance(policy, dict):
            _update_policy_field(policy, "preflight", preflight_payload)
            _update_policy_field(policy, "backend_decisions", decision_payload)
            if isinstance(policy.get("repair_loop"), dict):
                policy["repair_loop"]["cycle"] = 0
                repair_payload = dict(policy["repair_loop"])
            else:
                policy["repair_loop"] = repair_payload
            policy["policy_preflight_state"] = {
                "mode": mode,
                "status": result.status,
                "updated_at": datetime.now().isoformat(),
                "role": role,
                "roles": [role],
                "scan_mode": session_data.get("scan_mode"),
                "repair_cycle": repair_payload.get("cycle", 0),
            }
            scan_session._flush()

            task_id = policy.get("ledger_id")
            if isinstance(task_id, str) and task_id:
                try:
                    record_task_event(
                        _POLICY_LEDGER_DB,
                        task_id=task_id,
                        kind="preflight",
                        payload={
                            "role": role,
                            "status": result.status,
                            "mode": mode,
                            "scan_mode": session_data.get("scan_mode"),
                            "result": preflight_payload,
                            "decision": decision_payload,
                            "repair_loop": repair_payload,
                            "policy_preflight_state": policy.get("policy_preflight_state"),
                        },
                    )
                except Exception:
                    _log.exception("failed to record policy preflight event")

        return JSONResponse({
            "ok": True,
            "mode": mode,
            "role": role,
            "status": result.status,
            "marker": marker,
            "preflight": preflight_payload,
            "backend_decision": decision_payload,
            "policy_preflight_state": policy.get("policy_preflight_state") if isinstance(policy, dict) else {},
        })
    except Exception:
        _log.exception("failed to run policy preflight")
        return JSONResponse({"ok": False, "error": "request failed"}, status_code=500)


@router.post("/api/policy/launch-plan")
async def api_policy_launch_plan(payload: dict | None = None) -> JSONResponse:
    """Evaluate a role launch decision and enforce delegation guardrails."""
    payload = payload or {}
    role = _normalize_preflight_role(payload.get("role"))
    if not role:
        return JSONResponse({
            "ok": False,
            "error": "invalid role; must be explorer|executor|tester|reviewer|security review",
        }, status_code=400)

    intended_model = _normalize_string(payload.get("model") or payload.get("intended_model"))
    intended_effort = _normalize_string(payload.get("effort") or payload.get("intended_effort"))
    if not intended_model or not intended_effort:
        return JSONResponse({"ok": False, "error": "model and effort are required"}, status_code=400)

    explicit_worker_available = not _normalize_pref_bool(payload.get("prefer_native"), default=False)
    if "explicit_worker_available" in payload:
        explicit_worker_available = _normalize_pref_bool(
            payload.get("explicit_worker_available"),
            default=True,
        )

    try:
        from core import session as scan_session
        from core.session import resolve_launch_contract

        scan_session.load_from_disk(force=True)
        contract = resolve_launch_contract(
            role,
            intended_model=intended_model,
            intended_effort=intended_effort,
            explicit_worker_available=explicit_worker_available,
        )
        if not contract.get("enabled", False):
            return JSONResponse({
                "ok": False,
                "error": contract.get("reason", "policy launch disabled"),
                "enabled": False,
            }, status_code=409)
        if contract.get("action") in {"blocked", "needs_approval"}:
            return JSONResponse({
                "ok": False,
                "enabled": True,
                "decision": contract,
            }, status_code=423)
        return JSONResponse({"ok": True, "decision": contract})
    except Exception:
        _log.exception("failed to evaluate policy launch plan")
        return JSONResponse({"ok": False, "error": "request failed"}, status_code=500)
