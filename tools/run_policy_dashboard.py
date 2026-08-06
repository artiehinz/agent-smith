"""Run the dashboard UI and a lightweight policy/session API shim.

This module intentionally avoids a full web framework dependency so the repo
can run the dashboard even when framework versions are inconsistent.
"""

from __future__ import annotations

import json
import mimetypes
import re
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core import session as scan_session
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
    list_open_tasks,
    parse_preflight_output,
    record_task_event,
    run_preflight_probe,
    task_events,
)

INDEX_FILE = REPO_ROOT / "dashboard" / "index.html"
POLICY_LEDGER_DB = REPO_ROOT / ".codex-control" / "policy_task_ledger.sqlite"
INCLUDE_RE = re.compile(r"{%\s*include\s+'([^']+)'\s*%}")

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


def _coerce_int(raw: Any, *, default: int = 0) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _coerce_task_limit(raw: Any, *, default: int, minimum: int, maximum: int) -> int:
    value = _coerce_int(raw, default=default)
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


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


def _normalize_string(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    return value or None


def _normalize_route(raw: Any) -> str | None:
    value = str(raw or "").strip().lower()
    return value if value in _ALLOWED_ROUTES else None


def _normalize_pref_role(raw: Any) -> str | None:
    role = _normalize_string(raw)
    if not role:
        return None
    normalized = role.replace("_", " ").replace("-", " ").strip().lower()
    return normalized if normalized in _ALLOWED_PREFLIGHT_ROLES else None


def _load_session() -> dict[str, Any]:
    try:
        scan_session.load_from_disk(force=True)
        return scan_session.get() or {}
    except Exception:
        return {}


def _save_session(session: dict[str, Any] | None) -> None:
    if not session or not isinstance(session, dict):
        return
    try:
        scan_session._current = session  # noqa: SLF001
        scan_session._flush()  # noqa: SLF001
    except Exception:
        pass


def _policy_sections(raw: str) -> str:
    base = REPO_ROOT / "dashboard"

    def _replace(match: re.Match[str]) -> str:
        rel = match.group(1).strip()
        target = base / rel
        if target.exists():
            return target.read_text(encoding="utf-8")
        name = rel.split("/")[-1].replace(".html", "")
        return (
            f'<section class="tab-content" id="tab-{name}">'
            f'<div class="panel"><div class="empty-placeholder">Tab "{name}" is not available in this workspace.</div></div>'
            f"</section>"
        )

    return INCLUDE_RE.sub(_replace, raw)


def _safe_json(value: dict[str, Any] | list[Any] | None) -> Any:
    if value is None:
        return {}
    return value


def _terminal_status(status: str | None) -> bool:
    return status in {"complete", "incomplete_with_unresolved_blockers", "limit_reached"}


def _route_policy(session: dict[str, Any]) -> dict[str, Any]:
    policy = session.get("policy")
    if isinstance(policy, dict):
        return policy
    return {}


def _ensure_policy(session: dict[str, Any]) -> dict[str, Any]:
    policy = session.get("policy")
    if isinstance(policy, dict):
        return policy
    route = "direct"
    policy = {
        "route": route,
        "score": 0.0,
        "override_applied": False,
        "rationale": [],
        "details": {
            "task_breadth": 4,
            "affected_packages": 0,
            "uncertainty": 3,
            "verification_complexity": 5,
            "independent_work_opportunities": 1,
            "estimated_agent_overhead": 1,
        },
        "token_budget": {},
        "policy_engine": "route_classifier_v1",
    }
    session["policy"] = policy
    return policy


def _update_policy_field(policy: dict[str, Any], key: str, payload: dict[str, Any]) -> None:
    role = payload.get("role") or (payload.get("intent") or {}).get("role")
    if not isinstance(role, str) or not role.strip():
        return
    current = dict(policy.get(key) or {})
    current[str(role).strip()] = payload
    policy[key] = current


def _build_policy_preflight(payload: PreflightResult, marker_expected: str | None) -> dict[str, Any]:
    return attestation_payload(payload, marker_expected)


def _backend_decision_payload(role: str, decision, route: str | None = None, route_hint: str | None = None) -> dict[str, Any]:
    return {
        "role": decision.role if hasattr(decision, "role") else role,
        "selected_backend": decision.selected_backend.value,
        "fallback_backend": decision.fallback_backend.value if decision.fallback_backend else None,
        "fail_closed": decision.fail_closed,
        "requires_approval": decision.requires_approval,
        "route": route,
        "route_hint": route_hint,
        "reason": decision.reason,
    }


def _api_policy_payload() -> dict[str, Any]:
    session = _load_session()
    policy = session.get("policy")
    if isinstance(policy, dict):
        return policy
    return {}


def _write_json(handler: BaseHTTPRequestHandler, payload: dict[str, Any] | list[Any], status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _write_text(handler: BaseHTTPRequestHandler, body: str, content_type: str = "text/plain; charset=utf-8", status: int = 200) -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _write_redirect(handler: BaseHTTPRequestHandler, location: str) -> None:
    handler.send_response(302)
    handler.send_header("Location", location)
    handler.end_headers()


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = _coerce_int(handler.headers.get("Content-Length"), default=0)
    if length <= 0:
        return {}
    try:
        raw = handler.rfile.read(length).decode("utf-8")
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


class _DashboardHandler(BaseHTTPRequestHandler):
    def _serve_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "not found")
            return
        mime_type, _enc = mimetypes.guess_type(str(file_path))
        if file_path.suffix.lower() == ".js":
            mime = "application/javascript; charset=utf-8"
        elif file_path.suffix.lower() == ".css":
            mime = "text/css; charset=utf-8"
        elif file_path.suffix.lower() in {".png", ".ico"}:
            if file_path.suffix.lower() == ".ico":
                mime = "image/x-icon"
            else:
                mime = "image/png"
        else:
            mime = mime_type or "text/plain; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _serve_static(self, parsed_path: str) -> None:
        if parsed_path.startswith("/"):
            parsed_path = parsed_path[1:]
        file_path = REPO_ROOT / parsed_path
        if parsed_path.startswith("dashboard/"):
            if parsed_path == "dashboard":
                file_path = INDEX_FILE
            if file_path.is_dir():
                self.send_error(404, "not found")
                return
        self._serve_file(file_path)

    def _handle_api(self, path: str, method: str, payload: dict[str, Any] | None = None) -> None:
        session = _load_session()
        if not isinstance(session, dict):
            session = {}

        if path == "/api/session":
            if isinstance(session, dict):
                if session.get("triage_requested"):
                    session.setdefault("pending_adjudication", 0)
                    progress_at = session.get("triage_progress_at")
                    if isinstance(progress_at, (int, float)):
                        session["triage_idle_s"] = max(0, int(time.time() - float(progress_at)))
                return _write_json(self, session)
            return _write_json(self, {})

        if path == "/api/smith-status":
            status = session.get("status") if isinstance(session, dict) else None
            running = isinstance(status, str) and status in {"running", "intervention_required"}
            return _write_json(
                self,
                {"running": bool(running), "idle": False, "adjudicating": bool(session.get("triage_requested"))},
            )

        if path == "/api/intervention":
            intervention = session.get("intervention") if isinstance(session, dict) else None
            if isinstance(intervention, dict) and intervention:
                body = dict(intervention)
                body["active"] = True
                return _write_json(self, body)
            return _write_json(self, {"active": False})

        if path == "/api/intervention/respond":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            if not session:
                return _write_json(self, {"ok": False, "error": "no active session"}, status=409)
            if "intervention" in session and isinstance(session["intervention"], dict):
                session.pop("intervention", None)
            history = session.get("intervention_history")
            if not isinstance(history, list):
                history = []
            history.append({
                "ts": time.time(),
                "code": (payload or {}).get("choice", "manual"),
                "situation": (payload or {}).get("message", ""),
                "resolved_at": time.time(),
            })
            session["intervention_history"] = history
            _save_session(session)
            return _write_json(self, {"ok": True})

        if path == "/api/steer":
            return _write_json(self, {"ok": True})

        if path == "/api/smith-clients":
            return _write_json(self, {"active": "claude", "clients": ["claude", "gpt-5"]})

        if path == "/api/restart-smith":
            return _write_json(self, {"ok": True, "client": "claude", "pid": 0})

        if path == "/api/phase":
            phase = str(session.get("scan_phase") or "exploit")
            next_phase = {"exploit": "coverage", "coverage": "synthesis", "synthesis": None}.get(phase)
            return _write_json(self, {
                "phase": phase,
                "running": session.get("status") in {"running", "intervention_required"},
                "next": next_phase,
                "advice": False,
            })

        if path == "/api/phase/advance":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            current = str(session.get("scan_phase") or "exploit")
            target = str((payload or {}).get("target") or "").strip()
            next_map = {"exploit": "coverage", "coverage": "synthesis", "synthesis": "synthesis"}
            next_phase = target if target in {"coverage", "synthesis"} else next_map.get(current, "synthesis")
            if session:
                session["scan_phase"] = next_phase
                _save_session(session)
            return _write_json(self, {"ok": True, "from": current, "to": next_phase})

        if path == "/api/complete":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            if not session:
                return _write_json(self, {"ok": False, "error": "no active session"}, status=409)
            session["status"] = "complete"
            session.pop("triage_requested", None)
            _save_session(session)
            return _write_json(self, {"ok": True})

        if path == "/api/force-stop":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            if not session:
                return _write_json(self, {"ok": False, "error": "no active session"}, status=409)
            session["status"] = "incomplete_with_unresolved_blockers"
            session.pop("triage_requested", None)
            _save_session(session)
            return _write_json(self, {"ok": True, "killed": True, "pid": None})

        if path == "/api/triage":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            if not session:
                return _write_json(self, {"ok": False, "error": "no active session"}, status=409)
            session["triage_requested"] = True
            session["triage_progress_at"] = time.time()
            session["triage_pending_last"] = session.get("pending_adjudication", 0)
            session.setdefault("pending_adjudication", 0)
            session["status"] = session.get("status") or "intervention_required"
            _save_session(session)
            return _write_json(
                self,
                {
                    "ok": True,
                    "status": "triaging",
                    "pending_adjudication": session["pending_adjudication"],
                    "smith_spawned": True,
                },
            )

        if path == "/api/triage-cancel":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            if not session:
                return _write_json(self, {"ok": False, "error": "no active session"}, status=409)
            session["triage_requested"] = False
            session.pop("triage_progress_at", None)
            session.pop("triage_pending_last", None)
            _save_session(session)
            return _write_json(self, {"ok": True})

        if path == "/api/coverage":
            return _write_json(self, {
                "meta": {"total_cells": 0, "addressed": 0, "tested": 0},
                "cells": [],
            })

        if path == "/api/cost":
            limits = session.get("limits", {}) if isinstance(session, dict) else {}
            est = 0.0
            max_cost = limits.get("max_cost_usd")
            if isinstance(max_cost, (int, float)):
                est = max_cost / 10
            return _write_json(self, {"est_cost_usd": est})

        if path == "/api/policy":
            return _write_json(self, _safe_json(_api_policy_payload()))

        if path == "/api/policy/preflight":
            policy = _api_policy_payload()
            return _write_json(
                self,
                {
                    "ok": True,
                    "policy_route": policy.get("route") if isinstance(policy, dict) else None,
                    "preflight": policy.get("preflight", {}),
                    "backend_decisions": policy.get("backend_decisions", {}),
                    "policy_preflight_state": policy.get("policy_preflight_state", {}),
                },
            )

        if path == "/api/policy/route":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            route = _normalize_route((payload or {}).get("route"))
            if not route:
                return _write_json(
                    self,
                    {"ok": False, "error": "invalid route; must be direct|structured|parallel"},
                    status=400,
                )
            if not session:
                return _write_json(self, {"ok": False, "error": "no active session"}, status=409)
            policy = _ensure_policy(session)
            policy["route"] = route
            policy["route_hint"] = route
            policy["override_applied"] = True
            repair = policy.setdefault("repair_loop", {})
            repair.setdefault("max_cycles", 2)
            repair["cycle"] = 0

            _save_session(session)
            task_id = policy.get("ledger_id")
            if isinstance(task_id, str) and task_id:
                try:
                    from core.policy.task_ledger import record_task_event

                    record_task_event(
                        POLICY_LEDGER_DB,
                        task_id=task_id,
                        kind="route_override",
                        payload={"route": route, "source": "dashboard"},
                    )
                except Exception:
                    pass
            return _write_json(self, {"ok": True, "route": route, "policy": policy})

        if path == "/api/policy/repair":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            if not session:
                return _write_json(self, {"ok": False, "error": "no active session"}, status=409)
            policy = _ensure_policy(session)
            cycle_raw = (payload or {}).get("cycle")
            max_raw = (payload or {}).get("max_cycles")
            if cycle_raw is None and max_raw is None:
                return _write_json(
                    self,
                    {"ok": False, "error": "at least one of cycle or max_cycles is required"},
                    status=400,
                )
            repair = policy.setdefault("repair_loop", {})
            if cycle_raw is not None:
                repair["cycle"] = _coerce_int(cycle_raw, default=repair.get("cycle", 0))
            if max_raw is not None:
                repair["max_cycles"] = _coerce_task_limit(
                    max_raw,
                    default=repair.get("max_cycles", 2),
                    minimum=1,
                    maximum=20,
                )
            _save_session(session)
            return _write_json(self, {"ok": True, "repair_loop": repair})

        if path == "/api/policy/preflight":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            role = _normalize_pref_role((payload or {}).get("role"))
            if not role:
                return _write_json(
                    self,
                    {
                        "ok": False,
                        "error": "invalid role; must be explorer|executor|tester|reviewer|security review",
                    },
                    status=400,
                )
            intended_model = _normalize_string((payload or {}).get("model") or (payload or {}).get("intended_model"))
            intended_effort = _normalize_string((payload or {}).get("effort") or (payload or {}).get("intended_effort"))
            if not intended_model or not intended_effort:
                return _write_json(
                    self,
                    {"ok": False, "error": "model and effort are required"},
                    status=400,
                )
            role_sandbox = _normalize_string((payload or {}).get("sandbox")) or "read_only"
            explicit_worker_available = not _normalize_pref_bool((payload or {}).get("prefer_native"), default=False)
            if "explicit_worker_available" in (payload or {}):
                explicit_worker_available = _normalize_pref_bool(
                    (payload or {}).get("explicit_worker_available"),
                    default=True,
                )

            intent = PreflightIntent(
                role=role,
                model=intended_model,
                effort=intended_effort,
                sandbox=role_sandbox,
            )
            raw_output = _normalize_string((payload or {}).get("raw_output"))
            marker = _normalize_string((payload or {}).get("marker")) or generate_preflight_marker()
            mode = "auto"
            try:
                if raw_output:
                    mode = "manual"
                    result = parse_preflight_output(intent, raw_output, marker)
                else:
                    result = run_preflight_probe(intent, marker)
                marker = result.marker
                intended = ModelSpec(name=intended_model, effort=intended_effort)
                actual = (
                    ModelSpec(name=str(result.actual_model), effort=str(result.actual_effort))
                    if result.actual_model and result.actual_effort
                    else None
                )
                attestation = ModelAttestation(role=role, intended=intended, actual=actual)
                decision = choose_backend(
                    role=role,
                    intended_model=intended_model,
                    intended_effort=intended_effort,
                    attestation=attestation,
                    explicit_worker_available=explicit_worker_available,
                )
                if not isinstance(session, dict) or not session:
                    return _write_json(self, {"ok": False, "error": "no active session"}, status=409)
                policy = _ensure_policy(session)
                route = str(policy.get("route") or "direct")
                route_hint = policy.get("route_hint")
                if route_hint is not None:
                    route_hint = str(route_hint)
                decision_payload = _backend_decision_payload(role, decision, route=route, route_hint=route_hint)
                decision_payload["role"] = role
                decision_payload["route"] = route
                decision_payload["route_hint"] = route_hint
                decision_payload["status"] = "ok" if result.status == "match" else "issues_detected"
                decision_payload["mode"] = mode
                decision_payload["command"] = (
                    explicit_worker_args(model=intended_model, effort=intended_effort)
                    if decision.selected_backend.value == "explicit_codex_exec"
                    else None
                )

                preflight_payload = _build_policy_preflight(result, marker)
                preflight_payload["mode"] = mode
                preflight_payload["status"] = result.status
                preflight_payload["role"] = role
                preflight_payload["status"] = result.status
                _update_policy_field(policy, "preflight", preflight_payload)
                _update_policy_field(policy, "backend_decisions", decision_payload)
                repair_payload = policy.get("repair_loop") if isinstance(policy.get("repair_loop"), dict) else {"cycle": 0, "max_cycles": 2}
                if not isinstance(policy.get("repair_loop"), dict):
                    policy["repair_loop"] = repair_payload
                policy["policy_preflight_state"] = {
                    "mode": mode,
                    "status": result.status,
                    "updated_at": datetime.now().isoformat(),
                    "role": role,
                    "roles": [role],
                    "scan_mode": session.get("scan_mode"),
                    "repair_cycle": repair_payload.get("cycle", 0),
                }

                task_id = policy.get("ledger_id")
                if isinstance(task_id, str) and task_id:
                    try:
                        record_task_event(
                            POLICY_LEDGER_DB,
                            task_id=task_id,
                            kind="preflight",
                            payload={
                                "role": role,
                                "status": result.status,
                                "mode": mode,
                                "scan_mode": session.get("scan_mode"),
                                "result": preflight_payload,
                                "decision": decision_payload,
                                "repair_loop": repair_payload,
                                "policy_preflight_state": policy["policy_preflight_state"],
                            },
                        )
                    except Exception:
                        pass
                _save_session(session)

                return _write_json(self, {
                    "ok": True,
                    "mode": mode,
                    "role": role,
                    "status": result.status,
                    "marker": marker,
                    "preflight": preflight_payload,
                    "backend_decision": decision_payload,
                    "policy_preflight_state": policy["policy_preflight_state"],
                })
            except Exception:
                return _write_json(self, {"ok": False, "error": "request failed"}, status=500)

        if path == "/api/policy/launch-plan":
            if method != "POST":
                self.send_error(405, "method not allowed")
                return
            role = _normalize_pref_role((payload or {}).get("role"))
            if not role:
                return _write_json(
                    self,
                    {
                        "ok": False,
                        "error": "invalid role; must be explorer|executor|tester|reviewer|security review",
                    },
                    status=400,
                )
            intended_model = _normalize_string((payload or {}).get("model") or (payload or {}).get("intended_model"))
            intended_effort = _normalize_string((payload or {}).get("effort") or (payload or {}).get("intended_effort"))
            if not intended_model or not intended_effort:
                return _write_json(self, {"ok": False, "error": "model and effort are required"}, status=400)

            explicit_worker_available = not _normalize_pref_bool((payload or {}).get("prefer_native"), default=False)
            if "explicit_worker_available" in (payload or {}):
                explicit_worker_available = _normalize_pref_bool(
                    (payload or {}).get("explicit_worker_available"),
                    default=True,
                )

            contract = scan_session.resolve_launch_contract(
                role,
                intended_model=intended_model,
                intended_effort=intended_effort,
                explicit_worker_available=explicit_worker_available,
            )
            if not contract.get("enabled", False):
                return _write_json(self, {"ok": False, "error": contract.get("reason", "policy launch disabled"), "enabled": False}, status=409)
            if contract.get("action") in {"blocked", "needs_approval"}:
                return _write_json(self, {"ok": False, "enabled": True, "decision": contract}, status=423)
            return _write_json(self, {"ok": True, "decision": contract})

        if path.startswith("/api/policy/tasks"):
            if method != "GET":
                self.send_error(405, "method not allowed")
                return
            if path == "/api/policy/tasks":
                parsed = urllib.parse.urlparse(self.path)
                q = urllib.parse.parse_qs(parsed.query)
                status = (q.get("status", [None])[0] or None)
                owner = (q.get("owner_role", [None])[0] or None)
                route = (q.get("route", [None])[0] or None)
                since = _normalize_datetime((q.get("since", [None])[0] or None))
                until = _normalize_datetime((q.get("until", [None])[0] or None))
                limit = _coerce_task_limit(
                    q.get("limit", [None])[0],
                    default=50,
                    minimum=1,
                    maximum=250,
                )
                offset = _coerce_int(q.get("offset", [0])[0], default=0)
                tasks = list_open_tasks(
                    POLICY_LEDGER_DB,
                    status=status,
                    owner_role=owner,
                    route=route,
                    since=since,
                    until=until,
                    limit=limit,
                    offset=max(0, offset),
                )
                return _write_json(self, {"ok": True, "tasks": tasks, "count": len(tasks)})

            # /api/policy/tasks/<task_id>
            task_id = path.removeprefix("/api/policy/tasks/").strip()
            if not task_id:
                return _write_json(self, {"ok": False, "error": "task id required"}, status=400)
            entry = get_task_ledger(POLICY_LEDGER_DB, task_id)
            if not entry:
                return _write_json(self, {"ok": False, "error": "not found"}, status=404)
            events = task_events(POLICY_LEDGER_DB, task_id)
            return _write_json(
                self,
                {
                    "ok": True,
                    "task": entry,
                    "events": events,
                    "event_count": len(events),
                },
            )

        self.send_error(404, "not found")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/" or not path:
            return _write_redirect(self, "/dashboard/index.html")

        if path.startswith("/api/"):
            return self._handle_api(path, "GET")

        if path in {"/dashboard", "/dashboard/"}:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            body = _policy_sections(INDEX_FILE.read_text(encoding="utf-8"))
            data = body.encode("utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/dashboard/index.html":
            body = _policy_sections(INDEX_FILE.read_text(encoding="utf-8"))
            return _write_text(self, body, content_type="text/html; charset=utf-8")

        if path.startswith("/static/") or path.startswith("/favicon") or path in {
            "/favicon.ico",
            "/favicon-32x32.png",
            "/logo.png",
        }:
            return self._serve_static(path)

        if path in {"/dashboard/index.html", "/api/policy", "/api/policy/preflight"}:
            self._serve_static(path)
            return

        # Fallback static path under repo root (covers any directly loaded test assets).
        return self._serve_static(path)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        payload = _read_json_body(self)
        if path.startswith("/api/"):
            return self._handle_api(path, "POST", payload=payload)
        self.send_error(404, "not found")

    def log_message(self, fmt: str, *args: object) -> None:
        # silence noisy request logs by default; the UI already surfaces request state.
        return


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), _DashboardHandler)
    print(f"Policy dashboard running on http://{host}:{port}/dashboard/index.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down dashboard...")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
