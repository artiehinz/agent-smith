"""Policy and execution-route telemetry endpoints."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Path
from fastapi.responses import JSONResponse

import core.paths as _paths

from core.policy import (
    ModelAttestation,
    ModelSpec,
    PreflightIntent,
    PreflightResult,
    choose_backend,
    explicit_worker_args,
    generate_preflight_marker,
    get_task_ledger,
    list_open_tasks,
    parse_preflight_output,
    preflight_prompt,
    record_task_event,
    route_token_budget,
    task_events,
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


def _normalize_preflight_role(raw: Any) -> str | None:
    role = _normalize_string(raw)
    if not role:
        return None
    normalized = role.replace("_", " ").replace("-", " ").strip().lower()
    return normalized if normalized in _ALLOWED_PREFLIGHT_ROLES else None


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


def _attestation_payload(result: PreflightResult, marker_expected: str | None) -> dict[str, Any]:
    intended = {
        "role": result.intent.role,
        "model": result.intent.model,
        "effort": result.intent.effort,
        "sandbox": result.intent.sandbox,
    }
    actual = {
        "role": result.actual_role,
        "model": result.actual_model,
        "effort": result.actual_effort,
        "sandbox": result.actual_sandbox,
    }
    return {
        "status": result.status,
        "marker_expected": marker_expected,
        "marker": result.marker,
        "intended": intended,
        "actual": actual,
        "parse_error": result.parse_error,
        "raw_output": result.raw_output,
    }


def _backend_decision_payload(role: str, decision) -> dict[str, Any]:
    return {
        "role": decision.role,
        "selected_backend": decision.selected_backend.value,
        "fallback_backend": decision.fallback_backend.value if decision.fallback_backend else None,
        "fail_closed": decision.fail_closed,
        "requires_approval": decision.requires_approval,
        "reason": decision.reason,
    }


def _build_attestation(result: PreflightResult) -> ModelAttestation:
    intended = ModelSpec(name=result.intent.model, effort=result.intent.effort)
    actual = None
    if result.actual_model and result.actual_effort:
        actual = ModelSpec(name=result.actual_model, effort=result.actual_effort)
    return ModelAttestation(role=result.intent.role, intended=intended, actual=actual)


def _update_policy_field(policy: dict, key: str, value: dict[str, Any]) -> None:
    current = dict(policy.get(key) or {})
    current[value["role"]] = value
    policy[key] = current


def _policy_route_hint(policy: dict[str, Any] | None) -> str | None:
    if not isinstance(policy, dict):
        return None
    route = policy.get("route_hint")
    if route:
        return str(route)
    return None


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
        return JSONResponse({"ok": True, "preflight": {}, "backend_decisions": {}})

    return JSONResponse({
        "ok": True,
        "policy_route": _policy_route_hint(policy),
        "preflight": policy.get("preflight", {}),
        "backend_decisions": policy.get("backend_decisions", {}),
    })


@router.get("/api/policy/tasks")
async def api_policy_tasks() -> JSONResponse:
    """List persisted task-ledger rows for operator visibility."""
    try:
        tasks = list_open_tasks(_POLICY_LEDGER_DB)
        return JSONResponse({"ok": True, "tasks": tasks, "count": len(tasks)})
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
        scan_session._flush()

        task_id = policy.get("ledger_id")
        if isinstance(task_id, str) and task_id:
            try:
                event_payload = {
                    "route": route,
                    "source": "dashboard",
                }
                record_task_event(
                    _POLICY_LEDGER_DB,
                    task_id=task_id,
                    kind="route_override",
                    payload=event_payload,
                )
            except Exception:
                _log.exception("failed to record policy route override event")
        return JSONResponse({"ok": True, "route": route, "policy": policy})
    except Exception:
        _log.exception("failed to set policy route")
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

    intent = PreflightIntent(
        role=role,
        model=intended_model,
        effort=intended_effort,
        sandbox=_normalize_string(payload.get("sandbox")) or "read_only",
    )
    marker = _normalize_string(payload.get("marker")) or generate_preflight_marker()
    raw_output = _normalize_string(payload.get("raw_output"))
    if raw_output is None:
        raw_output = _normalize_string(payload.get("probe_output"))
    if raw_output is None:
        # Useful default for manual reporting paths that want copy/paste output only.
        raw_output = preflight_prompt(intent, marker)
        raw_output = f"{raw_output}\n{payload.get('probe_output', '')}".strip() if payload.get("probe_output") else raw_output

    try:
        from core import session as scan_session

        explicit_worker_available = not _normalize_pref_bool(
            payload.get("prefer_native"),
            default=False,
        ) if "prefer_native" in payload else _normalize_pref_bool(
            payload.get("explicit_worker_available"),
            default=True,
        )
        result = parse_preflight_output(intent, raw_output, marker)
        attestation = _build_attestation(result)
        decision = choose_backend(
            role=role,
            intended_model=intended_model,
            intended_effort=intended_effort,
            attestation=attestation,
            explicit_worker_available=explicit_worker_available,
        )

        preflight_payload = _attestation_payload(result, marker)
        decision_payload = _backend_decision_payload(role, decision)
        decision_payload["intent"] = {
            "role": role,
            "model": intended_model,
            "effort": intended_effort,
            "sandbox": intent.sandbox,
        }
        decision_payload["command"] = explicit_worker_args(
            model=intended_model,
            effort=intended_effort,
        )

        scan_session.load_from_disk(force=True)
        session_data = scan_session.get() or {}
        if isinstance(session_data, dict):
            policy = session_data.get("policy")
            if isinstance(policy, dict):
                _update_policy_field(policy, "preflight", preflight_payload)
                _update_policy_field(policy, "backend_decisions", decision_payload)
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
                                "result": preflight_payload,
                                "decision": decision_payload,
                            },
                        )
                    except Exception:
                        _log.exception("failed to record policy preflight event")

        return JSONResponse({
            "ok": True,
            "role": role,
            "status": result.status,
            "marker": marker,
            "preflight": preflight_payload,
            "backend_decision": decision_payload,
        })
    except Exception:
        _log.exception("failed to run policy preflight")
        return JSONResponse({"ok": False, "error": "request failed"}, status_code=500)
