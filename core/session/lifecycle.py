"""
Session lifecycle
=================
Scan start/complete, the live-state accessor (`get`), disk bootstrap
(`load_from_disk`), and the post-scan triage-flag helpers
(`set_triage_requested`, `note_triage_progress`).

Mutable state (``_current``, paths, ``PRESETS``) lives in the ``core.session``
package namespace so the suite can patch it as ``core.session.NAME``. This
module reaches it via ``import core.session as _sess`` and reads/rebinds
``_sess.<name>`` at call time — start()/load_from_disk() rebind
``_sess._current`` (the package attribute) exactly as the in-package versions
did, keeping every name patchable without introducing an import cycle.
"""
from __future__ import annotations

import logging
import json
import os
import shutil
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

import core.session as _sess
from core import paths as _paths
from core import cost as cost_tracker
from core.policy import (
    ModelAttestation,
    ModelSpec,
    PreflightIntent,
    RouteContext,
    attestation_payload,
    classify_route,
    choose_backend,
    explicit_worker_args,
    generate_preflight_marker,
    init_ledger,
    record_task_event,
    route_token_budget,
    run_preflight_probe,
    should_disable_delegation,
    upsert_task,
)

_POLICY_LEDGER_DB = _paths.REPO_ROOT / ".codex-control" / "policy_task_ledger.sqlite"
_SESSION_DEFAULT_PRESTART_PRELIGHT_ROLES = (
    "executor",
    "tester",
    "reviewer",
    "security review",
    "explorer",
)
_SESSION_PREFLIGHT_TARGETS_ENV = "SMITH_POLICY_PRELIGHT_ROLES"
_SESSION_PRELIGHT_MODES_ENV = "SMITH_SESSION_PRELIGHT_MODES"
_SESSION_PRELIGHT_DISABLE_AUTO = "SMITH_DISABLE_SESSION_PRELIGHT"

_DEFAULT_PRELIGHT_MODEL = "gpt-5.6-luna"
_DEFAULT_PRELIGHT_EFFORT_BY_PROFILE = {
    "quick": "low",
    "standard": "medium",
    "thorough": "high",
    "recon": "medium",
}

_LOG = logging.getLogger(__name__)

_ALLOWED_ROUTES = {"direct", "structured", "parallel"}


def _record_policy_completion_event(
    status: str,
    *,
    route: str | None = None,
    route_hint: str | None = None,
    route_reset_source: str | None = None,
    route_reset_applied: bool = False,
    route_after_reset: str | None = None,
    notes: str = "",
    stop_reason: str | None = None,
    quality_gate: str | None = None,
) -> None:
    """Record completion in the policy ledger when this run was launched with policy tracking."""
    if not _sess._current:
        return
    policy = _sess._current.get("policy") if isinstance(_sess._current, dict) else None
    if not isinstance(policy, dict):
        return
    task_id = policy.get("ledger_id")
    if not isinstance(task_id, str) or not task_id:
        return

    payload = {
        "status": status,
        "notes": notes,
        "route": route,
        "route_hint": route_hint,
        "route_reset_applied": route_reset_applied,
        "route_after_reset": route_after_reset,
        "route_reset_source": route_reset_source,
    }
    if stop_reason:
        payload["stop_reason"] = stop_reason
    if quality_gate:
        payload["quality_gate"] = quality_gate

    from core.policy import record_task_event

    try:
        record_task_event(
            _POLICY_LEDGER_DB,
            task_id=task_id,
            kind="completed",
            payload=payload,
        )
    except Exception:
        pass


def _normalize_pref_bool(raw: object, default: bool = False) -> bool:
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


def _normalize_route(raw: object | None) -> str:
    value = str(raw or "").strip().lower()
    return value if value in _ALLOWED_ROUTES else "direct"


def _policy_preflight_targets(scan_mode: str | None) -> tuple[str, ...]:
    if _normalize_pref_bool(os.environ.get(_SESSION_PRELIGHT_DISABLE_AUTO), default=False):
        return ()

    normalized_mode = (scan_mode or "").strip().lower()
    mode_selector = os.environ.get(_SESSION_PRELIGHT_MODES_ENV, "benchmark").strip().lower()
    allowed_modes = {mode.strip() for mode in mode_selector.split(",") if mode.strip()}
    if not allowed_modes:
        allowed_modes = {"benchmark"}
    normalized_mode_tokens = set(allowed_modes)
    if "all" in normalized_mode_tokens or "auto" in normalized_mode_tokens or "*" in normalized_mode_tokens:
        pass
    elif normalized_mode and normalized_mode not in normalized_mode_tokens:
        return ()

    explicit = os.environ.get(_SESSION_PREFLIGHT_TARGETS_ENV, "")
    explicit_roles = tuple(
        role.strip().lower() for role in explicit.split(",") if role.strip()
    )
    if explicit_roles:
        return tuple(r.replace("-", " ") for r in explicit_roles)
    return _SESSION_DEFAULT_PRESTART_PRELIGHT_ROLES


def _resolve_preflight_intent(role: str, model_profile: str | None) -> PreflightIntent:
    key = role.replace("-", "_").replace(" ", "_").upper()
    model = (
        os.environ.get(f"SMITH_POLICY_PRELIGHT_MODEL_{key}")
        or os.environ.get("SMITH_POLICY_PRELIGHT_MODEL")
        or _DEFAULT_PRELIGHT_MODEL
    )
    effort_default = _DEFAULT_PRELIGHT_EFFORT_BY_PROFILE.get(
        (model_profile or "").lower(),
        "medium",
    )
    effort = (
        os.environ.get(f"SMITH_POLICY_PRELIGHT_EFFORT_{key}")
        or os.environ.get("SMITH_POLICY_PRELIGHT_EFFORT")
        or effort_default
    )
    sandbox = (
        os.environ.get(f"SMITH_POLICY_PRELIGHT_SANDBOX_{key}")
        or os.environ.get("SMITH_POLICY_PRELIGHT_SANDBOX", "read_only")
    )
    return PreflightIntent(role=role, model=model, effort=effort, sandbox=sandbox)


def _build_policy_attestation(intent: PreflightIntent, result) -> ModelAttestation:
    actual = (
        ModelSpec(name=result.actual_model, effort=result.actual_effort)
        if result.actual_model
        else None
    )
    return ModelAttestation(role=intent.role, intended=ModelSpec(name=intent.model, effort=intent.effort), actual=actual)


def _build_backend_decision_payload(
    role: str,
    decision,
    route: str | None = None,
    route_hint: str | None = None,
    command: list[str] | None = None,
) -> dict[str, object]:
    return {
        "role": role,
        "selected_backend": decision.selected_backend.value,
        "fallback_backend": decision.fallback_backend.value if decision.fallback_backend else None,
        "fail_closed": decision.fail_closed,
        "requires_approval": decision.requires_approval,
        "reason": decision.reason,
        "route": route,
        "route_hint": route_hint,
        "command": command,
    }


def _init_policy_task_record(policy: dict[str, object], scan_mode: str | None) -> str:
    task_id = str(policy.get("ledger_id") or _sess._current.get("id") or uuid.uuid4())
    route = str(policy.get("route") or "direct")
    route_hint = policy.get("route_hint")
    try:
        init_ledger(_POLICY_LEDGER_DB)
        upsert_task(
            _POLICY_LEDGER_DB,
            task_id=task_id,
            route=route,
            owner_role="orchestrator",
            status="open",
            route_hint=str(route_hint) if route_hint else None,
            metadata={
                "scan_mode": scan_mode,
                "route_hint": route_hint,
                "depth": _sess._current.get("depth") if isinstance(_sess._current, dict) else None,
                "scope": (_sess._current.get("scope") if isinstance(_sess._current, dict) else None),
            },
        )
        record_task_event(
            _POLICY_LEDGER_DB,
            task_id=task_id,
            kind="started",
            payload={"route": route, "route_hint": route_hint, "scan_mode": scan_mode},
        )
        policy["ledger_id"] = task_id
        return task_id
    except Exception:
        _LOG.exception("failed to initialize policy task entry")
        return task_id


def _run_session_preflight_auto(policy: dict[str, object], scan_mode: str | None, model_profile: str | None) -> tuple[dict, dict]:
    preflight_by_role: dict[str, dict[str, object]] = {}
    backend_by_role: dict[str, dict[str, object]] = {}
    explicit_worker_available = shutil.which("codex") is not None
    if not policy or not isinstance(policy, dict):
        return preflight_by_role, backend_by_role
    route = str(policy.get("route") or "direct")
    route_hint = policy.get("route_hint")
    if route_hint is not None:
        route_hint = str(route_hint)
    roles = _policy_preflight_targets(scan_mode)
    if not roles:
        return preflight_by_role, backend_by_role

    for role in roles:
        try:
            intent = _resolve_preflight_intent(role, model_profile)
            marker = generate_preflight_marker()
            result = run_preflight_probe(intent, marker)
            attestation = _build_policy_attestation(intent, result)
            decision = choose_backend(
                role=role,
                intended_model=intent.model,
                intended_effort=intent.effort,
                attestation=attestation,
                explicit_worker_available=explicit_worker_available,
            )
            preflight_payload = attestation_payload(result, marker)
            command = (
                explicit_worker_args(model=intent.model, effort=intent.effort)
                if decision.selected_backend.value == "explicit_codex_exec"
                else None
            )
            backend_payload = _build_backend_decision_payload(role, decision, route=route, route_hint=route_hint)
            backend_payload["requires_approval"] = decision.requires_approval
            backend_payload["fail_closed"] = should_disable_delegation(
                decision.selected_backend,
                attestation=attestation,
            ) or decision.fail_closed
            backend_payload["command"] = command
            backend_payload["mode"] = "auto"
            preflight_by_role[role] = preflight_payload
            backend_by_role[role] = backend_payload
        except Exception:
            _LOG.exception("failed auto session preflight for role=%s", role)
            marker = generate_preflight_marker()
            preflight_by_role[role] = {
                "status": "missing_actual",
                "marker_expected": marker,
                "marker": marker,
                "intent": {"role": role, "model": _DEFAULT_PRELIGHT_MODEL, "effort": _DEFAULT_PRELIGHT_EFFORT_BY_PROFILE.get((model_profile or "").lower(), "medium"), "sandbox": "read_only"},
                "actual": {"role": None, "model": None, "effort": None, "sandbox": "read_only"},
                "parse_error": "preflight failed",
                "raw_output": "",
                "mode": "auto",
            }
            backend_by_role[role] = {
                "role": role,
                "selected_backend": "native_subagent",
                "fallback_backend": None,
                "fail_closed": True,
                "requires_approval": False,
                "reason": "session auto preflight failed",
                "mode": "auto",
                "command": None,
                "route": route,
                "route_hint": route_hint,
            }
    return preflight_by_role, backend_by_role


def _finalize_terminal_session(
    final_status: str,
    *,
    notes: str | None = None,
    stop_reason: str | None = None,
    quality_gate: str | None = None,
    route_reset_source: str = "completion",
) -> None:
    """Finalize terminal session state and apply policy reset side-effects.

    This runs both manual completion and hard-limit terminal transitions so all
    policy bookkeeping (completion event + optional route reset) stays
    consistent regardless of stop path.
    """
    if not _sess._current or _sess._current["status"] not in ("running", "intervention_required"):
        return

    _sess._current["status"] = final_status
    if notes is not None:
        _sess._current["notes"] = notes
    _sess._current["finished"] = datetime.now(timezone.utc).isoformat()
    if quality_gate:
        _sess._current["quality_gate"] = quality_gate
    if stop_reason is not None:
        _sess._current["stop_reason"] = stop_reason

    reset_policy = None
    policy = _sess._current.get("policy")
    route = None
    route_hint = None
    route_after_reset: str | None = None
    if isinstance(policy, dict):
        route = str(policy.get("route")) if policy.get("route") is not None else None
        route_hint = str(policy.get("route_hint")) if policy.get("route_hint") is not None else None
        reset_policy = _reset_policy_on_completion(
            policy,
            depth=str(_sess._current.get("depth", "standard")),
            scope=_sess._current.get("scope") if isinstance(_sess._current.get("scope"), list) else None,
        )
        route_after_reset = str(reset_policy["reset_route"]) if reset_policy else None
    _record_policy_completion_event(
        final_status,
        route=route,
        route_hint=route_hint,
        route_reset_source=route_reset_source if reset_policy else None,
        route_reset_applied=bool(reset_policy),
        route_after_reset=route_after_reset,
        notes=notes or "",
        stop_reason=stop_reason,
        quality_gate=quality_gate,
    )
    if isinstance(policy, dict):
        policy["route_reset_applied"] = bool(reset_policy)
        policy["route_reset_source"] = route_reset_source if reset_policy else None
        policy["route_after_reset"] = route_after_reset
    if reset_policy and isinstance(policy, dict):
        task_id = policy.get("ledger_id")
        if isinstance(task_id, str) and task_id:
            try:
                from core.policy import record_task_event

                record_task_event(
                    _POLICY_LEDGER_DB,
                    task_id=task_id,
                    kind="route_reset",
                    payload={
                        "source": route_reset_source,
                        "previous_route": reset_policy["previous_route"],
                        "previous_route_hint": reset_policy["previous_route_hint"],
                        "route": reset_policy["reset_route"],
                        "notes": "policy route reset after task completion",
                    },
                )
            except Exception:
                pass

    _sess._flush()
    # Scan ended (human complete/force-complete or hard limit): snapshot the final
    # findings into the durable training bundle (self-contained), then tear down
    # RCE containers.
    snapshot_training_bundle()
    stop_pentest_containers()


def _reset_policy_on_completion(policy: dict[str, object], depth: str, scope: list[str] | None) -> dict[str, str] | None:
    """Reset manual route controls at task completion so overrides do not carry across tasks."""
    if not isinstance(policy, dict):
        return None

    previous_route = policy.get("route")
    previous_hint = policy.get("route_hint")
    if not bool(policy.get("override_applied")) and previous_hint is None:
        return None

    baseline = _default_route_policy(depth, scope or [])
    policy["route"] = baseline["route"]
    policy["score"] = baseline["score"]
    policy["rationale"] = baseline["rationale"]
    policy["details"] = baseline["details"]
    policy["token_budget"] = baseline["token_budget"]
    policy["policy_engine"] = baseline["policy_engine"]
    policy["override_applied"] = False
    policy.pop("route_hint", None)

    return {
        "previous_route": str(previous_route) if previous_route is not None else "",
        "previous_route_hint": str(previous_hint) if previous_hint is not None else "",
        "reset_route": str(baseline["route"]),
    }


def _parse_lhost(raw: str) -> tuple[str, int]:
    """Parse SMITH_LHOST into (host, port). Handles IPv4/hostname 'host[:port]' AND IPv6
    (bracketed '[2001:db8::1]:4444' or bare '::1'). Returns ('', 4444) for an unusable value
    (caller skips storing it). Default port 4444; anything outside 1..65535 falls back to 4444.
    Plain str.partition(':') was wrong for IPv6 — '::1' yielded host='' and '[::1]:4444' host='['."""
    raw = (raw or "").strip()
    port = 4444
    host = raw
    if raw.startswith("["):                       # bracketed IPv6, optional :port
        end = raw.find("]")
        if end != -1:
            host = raw[1:end]
            rest = raw[end + 1:]
            if rest.startswith(":") and rest[1:].isdigit():
                port = int(rest[1:])
    elif raw.count(":") == 1:                      # host:port (IPv4 / hostname)
        h, _, p = raw.partition(":")
        host = h
        if p.isdigit():
            port = int(p)
    # else: bare IPv6 (>=2 colons) or bare host → the whole string is the host, default port
    host = host.strip()
    if not (1 <= port <= 65535):
        port = 4444
    return host, port


def _default_route_policy(depth: str, scope: list[str] | None) -> dict[str, object]:
    """Build a conservative default route policy from launch intent."""
    depth_hint = {"quick": 2, "recon": 2, "standard": 4, "thorough": 7}.get(
        (depth or "standard").lower(), 4
    )
    context = RouteContext(
        task_breadth=depth_hint,
        affected_packages=min(8, max(0, len(scope or []))),
        uncertainty=3,
        verification_complexity=depth_hint + 1,
        independent_work_opportunities=1 if (scope or []) else 0,
        estimated_agent_overhead=1 if depth_hint != 7 else 2,
        route_hint=None,
    )
    decision = classify_route(context)
    budget = route_token_budget(decision.route.value)
    return {
        "route": decision.route.value,
        "score": decision.score,
        "override_applied": decision.override_applied,
        "rationale": decision.rationale,
        "details": decision.details,
        "token_budget": asdict(budget),
        "policy_engine": "route_classifier_v1",
    }


def policy_launch_plan(
    role: str,
    intended_model: str,
    intended_effort: str,
    *,
    explicit_worker_available: bool = True,
) -> dict[str, object]:
    """Build a structured launch decision for a role using active policy state."""
    if not _sess._current:
        return {"enabled": False, "reason": "no active session"}
    if not isinstance(role, str) or not role.strip():
        return {"enabled": False, "reason": "invalid role"}

    normalized_role = role.strip().lower()
    policy = _sess._current.get("policy")
    route = "direct"
    preflight_payload = None
    route_hint = None
    if isinstance(policy, dict):
        route = _normalize_route(policy.get("route"))
        raw_route_hint = policy.get("route_hint")
        if raw_route_hint is not None:
            route_hint = str(raw_route_hint)
        preflight_payload = policy.get("preflight")
        if isinstance(preflight_payload, dict):
            preflight_payload = preflight_payload.get(normalized_role)

    if not isinstance(preflight_payload, dict):
        preflight_payload = {}

    intent_payload = preflight_payload.get("intent", {})
    actual_payload = preflight_payload.get("actual", {})
    if (
        isinstance(intent_payload, dict)
        and intent_payload.get("model")
        and intent_payload.get("effort")
    ):
        intended_spec = ModelSpec(
            name=str(intent_payload["model"]),
            effort=str(intent_payload["effort"]),
        )
        actual_spec = (
            ModelSpec(name=str(actual_payload["model"]), effort=str(actual_payload["effort"]))
            if isinstance(actual_payload, dict) and actual_payload.get("model") and actual_payload.get("effort")
            else None
        )
        attestation = ModelAttestation(role=normalized_role, intended=intended_spec, actual=actual_spec)
    else:
        intended_spec = ModelSpec(name=intended_model, effort=intended_effort)
        attestation = ModelAttestation(
            role=normalized_role,
            intended=intended_spec,
            actual=(
                ModelSpec(name=str(actual_payload.get("model")), effort=str(actual_payload.get("effort")))
                if isinstance(actual_payload, dict) and actual_payload.get("model") and actual_payload.get("effort")
                else None
            ),
        )

    decision = choose_backend(
        normalized_role,
        intended_model=intended_spec.name,
        intended_effort=intended_spec.effort,
        attestation=attestation,
        explicit_worker_available=explicit_worker_available,
    )
    should_block = bool(decision.fail_closed)
    payload = {
        "enabled": True,
        "role": normalized_role,
        "route": route,
        "route_hint": route_hint,
        "selected_backend": decision.selected_backend.value,
        "fallback_backend": decision.fallback_backend.value if decision.fallback_backend else None,
        "requires_approval": decision.requires_approval,
        "fail_closed": decision.fail_closed,
        "block_delegation": should_block,
        "reason": decision.reason,
    }
    if decision.selected_backend.value == "explicit_codex_exec":
        payload["command"] = explicit_worker_args(
            model=intended_spec.name,
            effort=intended_spec.effort,
        )
    else:
        payload["command"] = None
    return payload


def evaluate_policy_launch(
    role: str,
    intended_model: str,
    intended_effort: str,
    *,
    explicit_worker_available: bool = True,
) -> dict[str, object]:
    """Return a launch decision and apply delegation policy side-effects."""
    decision = policy_launch_plan(
        role,
        intended_model,
        intended_effort,
        explicit_worker_available=explicit_worker_available,
    )
    if not decision.get("enabled", False):
        return decision

    role_key = str(decision["role"])
    status = "authorized"
    event = "delegation_authorized"
    if decision.get("block_delegation"):
        status = "blocked"
        event = "delegation_blocked"
    elif decision.get("requires_approval"):
        status = "needs_approval"
        event = "delegation_needs_approval"

    decision["status"] = status
    decision["action"] = status
    if isinstance(_sess._current, dict):
        policy = _sess._current.get("policy")
        if isinstance(policy, dict):
            decisions = dict(policy.get("backend_decisions") or {})
            decisions[role_key] = {
                "role": role_key,
                "route": decision.get("route"),
                "route_hint": decision.get("route_hint"),
                "selected_backend": decision.get("selected_backend"),
                "fallback_backend": decision.get("fallback_backend"),
                "requires_approval": decision.get("requires_approval"),
                "fail_closed": decision.get("fail_closed"),
                "reason": decision.get("reason"),
                "command": decision.get("command"),
                "status": status,
                "mode": "launch",
            }
            policy["backend_decisions"] = decisions

            task_id = policy.get("ledger_id")
            if isinstance(task_id, str) and task_id:
                try:
                    record_task_event(
                        _POLICY_LEDGER_DB,
                        task_id=task_id,
                        kind=event,
                        payload=dict(decision),
                    )
                except Exception:
                    _LOG.exception("failed to record policy launch event")
            _sess._flush()
    return decision


def resolve_launch_contract(
    role: str,
    intended_model: str,
    intended_effort: str,
    *,
    explicit_worker_available: bool = True,
) -> dict[str, object]:
    """Return an authoritative launch contract for orchestration boundaries.

    External callers should treat this as the execution contract before selecting
    a launch path or subprocess invocation.
    """
    decision = evaluate_policy_launch(
        role,
        intended_model=intended_model,
        intended_effort=intended_effort,
        explicit_worker_available=explicit_worker_available,
    )
    if not isinstance(decision, dict):
        return {"ok": False, "error": "invalid policy decision"}

    status = str(decision.get("status", "unknown"))
    selected_backend = str(decision.get("selected_backend", ""))
    explicit_backend = selected_backend == "explicit_codex_exec"

    return {
        "ok": status == "authorized",
        "launch_authorized": status == "authorized",
        "enabled": bool(decision.get("enabled", False)),
        "role": decision.get("role"),
        "route": decision.get("route"),
        "route_hint": decision.get("route_hint"),
        "selected_backend": decision.get("selected_backend"),
        "fallback_backend": decision.get("fallback_backend"),
        "requires_approval": bool(decision.get("requires_approval", False)),
        "fail_closed": bool(decision.get("fail_closed", False)),
        "block_delegation": bool(decision.get("block_delegation", False)),
        "reason": decision.get("reason"),
        "status": status,
        "action": decision.get("action"),
        "command": decision.get("command") if explicit_backend else None,
        "launch_command": decision.get("command") if explicit_backend else None,
        "command_path": "codex exec" if explicit_backend else "native_subagent",
        "requires_runtime_proxy": not explicit_backend,
    }


def enforce_launch_contract(
    role: str,
    intended_model: str,
    intended_effort: str,
    *,
    explicit_worker_available: bool = True,
) -> dict[str, object]:
    """Return an execution-ready decision with action-only contract semantics.

    The caller should treat any non-`authorized` action as a hard gate and avoid
    launching workers until policy state changes.
    """
    contract = resolve_launch_contract(
        role,
        intended_model=intended_model,
        intended_effort=intended_effort,
        explicit_worker_available=explicit_worker_available,
    )
    action_raw = str(contract.get("action") or contract.get("status", "blocked")).strip()
    action = action_raw if action_raw in {"authorized", "needs_approval", "blocked"} else "blocked"

    if action == "authorized":
        return {
            "ok": True,
            "action": action,
            "contract": contract,
            "launch": True,
            "status": contract.get("status"),
        }
    if action == "needs_approval":
        return {
            "ok": False,
            "action": action,
            "contract": contract,
            "launch": False,
            "requires_approval": True,
            "status": contract.get("status"),
        }

    return {
        "ok": False,
        "action": action,
        "contract": contract,
        "launch": False,
        "status": contract.get("status"),
        "reason": contract.get("reason", "policy launch blocked"),
    }


def enforce_and_execute_launch(
    role: str,
    intended_model: str,
    intended_effort: str,
    launch_executor,
    *,
    explicit_worker_available: bool = True,
    **launch_kwargs,
) -> dict[str, object]:
    """Evaluate policy and invoke `launch_executor` only on authorization.

    `launch_executor` receives the approved `contract` and must return a mapping
    describing launch result details. This function injects no launch semantics of
    its own and is therefore safe for external orchestration wiring.
    """
    gate = enforce_launch_contract(
        role,
        intended_model=intended_model,
        intended_effort=intended_effort,
        explicit_worker_available=explicit_worker_available,
    )
    if not isinstance(gate, dict) or not gate.get("launch"):
        return gate

    contract = gate.get("contract")
    if not isinstance(contract, dict):
        return {
            "ok": False,
            "action": "blocked",
            "status": "blocked",
            "reason": "policy contract missing",
            "launch": False,
            "contract": None,
        }
    execution = launch_executor(contract=contract, **launch_kwargs)
    return {
        "ok": True,
        "action": "authorized",
        "status": "authorized",
        "launch": True,
        "contract": contract,
        "execution": execution,
    }


def start(
    target:           str,
    depth:            str        = "standard",
    scope:            list[str]  | None = None,
    out_of_scope:     list[str]  | None = None,
    max_cost_usd:     float | None = None,
    max_time_minutes: int   | None = None,
    max_tool_calls:   int   | None = None,
    skill:            str   | None = None,
    model_profile:    str   | None = None,
    scan_mode:        str        = "pentest",
) -> dict:
    """scan_mode: "pentest" (default) — HIR pauses for human decisions on ambiguous situations.
                  "benchmark" — fully autonomous, no HIR triggers, aggressive exploitation.

    model_profile: full|medium|small, or None to AUTO-DETECT from the environment
                   (model name in OPENCODE_MODEL/OLLAMA_MODEL/MODEL/…, or a
                   SMITH_MODEL_PROFILE override). Auto-detection scopes the
                   context window so a forgotten flag on a small local model
                   (e.g. Qwen3-27B) doesn't silently overflow — it resolves to
                   'full' when no local signal is present (cloud Claude/GPT)."""
    """Initialise a new scan session and write session.json."""

    # Resolve the model profile: an explicit value wins; otherwise auto-detect
    # from the environment. Stored alongside the human-readable reason so the
    # operator can see (and override) what was picked.
    from core.model_detect import detect_profile
    resolved_profile, profile_reason = detect_profile(model_profile)

    # Reset cost/call counters from any previous session
    cost_tracker.reset()

    preset = _sess.PRESETS.get(depth, _sess.PRESETS["standard"])
    limits = {
        "max_cost_usd":     max_cost_usd     if max_cost_usd     is not None else preset["max_cost_usd"],
        "max_time_minutes": max_time_minutes  if max_time_minutes is not None else preset["max_time_minutes"],
        "max_tool_calls":   max_tool_calls    if max_tool_calls   is not None else preset["max_tool_calls"],
    }

    _sess._current = {
        "id":           str(uuid.uuid4()),
        "target":       target,
        "depth":        depth,
        "depth_label":  preset["label"],
        "description":  preset["description"],
        "scope":        scope        or [target],
        "out_of_scope": out_of_scope or [],
        "started":      datetime.now(timezone.utc).isoformat(),
        "finished":     None,
        "status":       "running",   # running | limit_reached | complete
        "stop_reason":  None,
        "limits":       limits,
        "skill":         skill,
        "skill_history": [
            {
                "skill":        skill,
                "reason":       "session start",
                "chained_from": None,
                "timestamp":    datetime.now(timezone.utc).isoformat(),
            }
        ] if skill else [],
        "tools_called":  [],
        "current_step":  None,
        # Three-phase scan model: exploit (deep, matrix-free) → coverage (matrix breadth)
        # → synthesis (compose everything). Saturation-driven; see core/session/phases.py.
        "scan_phase":    "exploit",
        "gates":         [],          # triggered gates that block completion
        "deferred_gates": [],         # gate IDs suppressed while a skill is active
        "setup_gates":   [],          # manual-setup prerequisites (capabilities.yaml) — NON-blocking, distinct from gates
        "spider_failures": {},        # targets where spider failed; cleared on success
        "model_profile": resolved_profile,
        "model_profile_reason": profile_reason,
        "scan_mode":     scan_mode,
        "policy":       _default_route_policy(depth, scope or []),
        "tool_invocations": [],
        "known_assets": {
            "domains": [], "ips": [], "ports": [],
            "technologies": [], "endpoints": [],
            # Authentication context — discovered creds, JWTs, and login endpoints.
            # Smith reads these (surfaced in recovery brief) when an endpoint
            # returns 401/403 instead of marking the cell "tested_clean".
            "credentials":    [],   # [{username, password, source}]
            "auth_tokens":    [],   # [{type, value, user_id?, role?, obtained_at}]
            "auth_endpoints": [],   # [{path, method, body_template}]
            # Out-of-band callbacks minted for blind-vuln confirmation. Survives
            # compaction (recovery brief) so a callback fired now can be polled later.
            "oob_interactions": [], # [{subdomain, correlation_id, linked_cell_id, minted_at, polled, hits}]
            # Connected test devices/emulators a readiness probe confirmed live.
            # Lets a setup_gate auto-satisfy its re-prompt across skills (never the probe).
            "devices": [],          # [{kind, serial, transport, source, obtained_at}]
        },
        # SM-1: seed with the always-resident overhead (system prompt + tool
        # schemas + CLAUDE.md/AGENTS.md) instead of counting tool output from 0 —
        # otherwise the meter reads ~10% while the window is near full and the
        # recovery directive never fires in time on a small model.
        "context_chars_sent": _sess._fixed_context_overhead_chars(),
        "complete_attempts":  0,        # incremented each time session(complete) is called
    }
    # Operator-provided reverse-shell listener (SMITH_LHOST="host[:port]") — a routable attacker
    # endpoint the target can call back to. Stored as a known asset so /reverse-shell uses a REAL
    # LHOST instead of a placeholder; when unset, the skill falls back to the OOB collaborator as
    # the callback rendezvous (and the QA guard flags placeholder-LHOST payloads).
    _lhost = os.environ.get("SMITH_LHOST", "").strip()
    if _lhost:
        _host, _port = _parse_lhost(_lhost)
        if _host:   # skip a malformed value rather than store a broken asset the model would use
            _sess._current["known_assets"]["attacker_host"] = {
                "lhost": _host, "lport": _port, "source": "SMITH_LHOST",
            }

    # Capture which Smith process drove this start() call so the dashboard
    # watchdog can ask "is THIS PID still alive?" instead of falling back to
    # the quick_log mtime heuristic (which gives false positives during long
    # thinking-mode reasoning).
    caller = _sess._detect_smith_caller()
    if caller:
        _sess._current["smith_proc"] = {
            **caller,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source":      "interactive_mcp",
        }
        _sess._persist_smith_caller(caller)

    # Materialize policy telemetry and task ledger baseline before the first
    # poll/update cycle can observe missing policy IDs.
    policy = _sess._current.get("policy")
    if isinstance(policy, dict):
        _init_policy_task_record(policy, scan_mode=scan_mode)
        if _policy_preflight_targets(scan_mode):
            preflight_results, decision_results = _run_session_preflight_auto(
                policy,
                scan_mode=scan_mode,
                model_profile=resolved_profile,
            )
        if preflight_results:
            policy["preflight"] = preflight_results
        if decision_results:
            policy["backend_decisions"] = decision_results
        preflight_status = "completed"
        if preflight_results and any(
            result.get("status") != "match" for result in preflight_results.values()
        ):
            preflight_status = "issues_detected"
        policy["policy_preflight_state"] = {
            "mode": "session_start",
            "status": preflight_status,
            "scan_mode": scan_mode,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "roles": list(preflight_results.keys()),
        }
            if preflight_results and isinstance(policy.get("repair_loop"), dict):
                policy["repair_loop"]["cycle"] = 0
            elif "repair_loop" in policy:
                policy["repair_loop"] = {"cycle": 0, "max_cycles": 2}
            task_id = policy.get("ledger_id")
            if isinstance(task_id, str) and task_id:
                for role, decision_payload in decision_results.items():
                    payload = {
                        "mode": "session_start",
                        "scan_mode": scan_mode,
                        "role": role,
                        "status": preflight_results.get(role, {}).get("status", "unknown"),
                        "result": preflight_results.get(role, {}),
                        "decision": decision_payload,
                        "repair_cycle": policy.get("repair_loop", {}).get("cycle") if isinstance(policy.get("repair_loop"), dict) else 0,
                    }
                    try:
                        record_task_event(
                            _POLICY_LEDGER_DB,
                            task_id=task_id,
                            kind="preflight",
                            payload=payload,
                        )
                    except Exception:
                        _LOG.exception("failed to record session preflight event")
    _sess._flush()
    return _sess._current


def stop_pentest_containers() -> None:
    """When a scan reaches a terminal state, stop the command-execution containers
    (Kali / Metasploit / MobSF) so a finished scan leaves NO running RCE endpoint.

    Best-effort, fast (short SIGTERM grace), and never raises into the completion path.
    Opt out with SMITH_KEEP_CONTAINERS=1 (e.g. to inspect a container after a scan).
    Lazy imports keep core.session free of a top-level dependency on tools/."""
    if os.environ.get("SMITH_KEEP_CONTAINERS", "").strip().lower() in ("1", "true", "yes"):
        return
    try:
        import subprocess
        from tools.docker_cli import docker_executable
        from tools.kali_runner import KALI_CONTAINER
        from tools.metasploit_runner import MSF_CONTAINER
        from tools.mobsf_runner import MOBSF_CONTAINER
        subprocess.run(
            [docker_executable(), "stop", "-t", "3",
             KALI_CONTAINER, MSF_CONTAINER, MOBSF_CONTAINER],
            capture_output=True, timeout=40, check=False,
        )
    except Exception:
        pass


def snapshot_training_bundle() -> None:
    """When a scan reaches a terminal state, copy the final findings.json into the
    engagement's durable training bundle (logs/smith-events/<id>/findings.json) so the
    bundle is self-contained — events + raw artifacts + meta + the adjudicated findings.

    Best-effort and never raises into the completion path. No-op when the event emitter is
    disabled (no bundle to complete). Lazy import keeps core.session free of a top-level
    dependency on mcp_server/."""
    try:
        from mcp_server.scan_engine.smith_events import snapshot_findings
        snapshot_findings()
    except Exception:
        pass


def complete(
    notes: str = "",
    stop_reason: str | None = None,
    quality_gate: str | None = None,
) -> dict:
    """Mark the scan as done (called by Claude when finished).

    quality_gate="failed" sets status to "incomplete_with_unresolved_blockers"
    so dashboards and exports can distinguish a force-completed scan from a clean one.
    A running→terminal transition also stops the pentest containers (below).
    """
    _sess._reconcile_if_external_write()
    final_status = "incomplete_with_unresolved_blockers" if quality_gate == "failed" else "complete"
    _finalize_terminal_session(
        final_status,
        notes=notes,
        stop_reason=stop_reason,
        quality_gate=quality_gate,
        route_reset_source="completion",
    )
    return _sess._current or {}


def set_triage_requested(value: bool = True) -> None:
    """Mark/clear that a standalone triage (adjudication) pass is in flight.

    Drives the dashboard's adjudication banner. Set when the operator triggers
    POST /api/triage; cleared (by api_session self-heal) once every in-scope
    finding carries a verdict. Triage never completes the scan, so there is no
    force_complete coupling — completion stays an independent operator action.
    """
    _sess._reconcile_if_external_write()
    if not _sess._current:
        return
    if value:
        # Triage is a post-scan step now: the flag must be settable on a STOPPED
        # scan (status complete/limit_reached/...), not only while running. Any
        # live session can carry it; completion never clears it.
        if _sess._current.get("status"):
            _sess._current["triage_requested"] = True
            # Stall clock: stamped now and re-stamped whenever a verdict lands
            # (see note_triage_progress). The dashboard flips the banner to a
            # "stalled" warning when this stops advancing — a progress signal
            # that, unlike the MCP heartbeat, isn't fooled by Smith staying
            # busy on unrelated testing while the triage pass is abandoned.
            now = time.time()
            _sess._current["triage_requested_at"] = now
            _sess._current["triage_progress_at"] = now
            _sess._current.pop("triage_pending_last", None)
            _sess._flush()
    else:
        _sess._current.pop("triage_requested", None)
        _sess._current.pop("triage_requested_at", None)
        _sess._current.pop("triage_progress_at", None)
        _sess._current.pop("triage_pending_last", None)
        _sess._flush()


def note_triage_progress(pending_count: int) -> None:
    """Advance the triage stall clock when the pending-verdict count drops.

    Called from the /api/session self-heal with the live pending count. The
    clock resets only on real progress (count decreased, or first observation),
    so a slow-but-advancing pass never looks stalled, while a pass that stops
    making verdicts — whether Smith went idle or wandered off to other work —
    trips the dashboard's stalled warning after the threshold.
    """
    if not _sess._current or not _sess._current.get("triage_requested"):
        return
    last = _sess._current.get("triage_pending_last")
    if last is None or pending_count < last:
        _sess._current["triage_pending_last"] = pending_count
        _sess._current["triage_progress_at"] = time.time()
        _sess._flush()


def get() -> dict | None:
    return _sess._current


def load_from_disk(force: bool = False) -> dict | None:
    """Populate _current from session.json.

    Used by processes (e.g. the dashboard API server) that never called
    start() but need to read/mutate session state.

    Default behavior loads only when _current is None (one-shot bootstrap).
    Pass force=True to ALWAYS reload from disk — required for the dashboard
    process whose in-memory _current goes stale as the MCP process keeps
    writing to session.json from another process.
    """
    if force:
        # force=True means "make _current match disk reality, whatever
        # that is". If the file was deleted (dashboard Clear All), drop
        # the cache so callers don't keep operating on stale state.
        # Gated on _last_local_write_mtime > 0 so test fixtures that
        # monkeypatch _current without ever flushing don't get
        # clobbered: in those tests we never saw disk, so its absence
        # isn't a deletion to mirror.
        if _sess._SESSION_FILE.exists():
            try:
                _sess._current = json.loads(_sess._SESSION_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        elif _sess._last_local_write_mtime > 0:
            _sess._current = None
        return _sess._current
    if _sess._current is None and _sess._SESSION_FILE.exists():
        try:
            _sess._current = json.loads(_sess._SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _sess._current
