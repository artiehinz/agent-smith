"""Session state package for policy runtime wiring."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from core import paths as _paths

_REPO_ROOT = _paths.REPO_ROOT
_SESSION_FILE = _REPO_ROOT / "session.json"
_SMITH_CALLER_FILE = _REPO_ROOT / ".codex-control" / "smith_caller.json"

_current: dict | None = None
_last_local_write_mtime: float = 0.0

PRESETS = {
    "quick": {
        "label": "quick",
        "description": "short, bounded run",
        "max_cost_usd": None,
        "max_time_minutes": 60,
        "max_tool_calls": 500,
    },
    "standard": {
        "label": "standard",
        "description": "balanced default run",
        "max_cost_usd": None,
        "max_time_minutes": 180,
        "max_tool_calls": 1400,
    },
    "thorough": {
        "label": "thorough",
        "description": "deep, long-running run",
        "max_cost_usd": None,
        "max_time_minutes": 360,
        "max_tool_calls": 2500,
    },
    "recon": {
        "label": "recon",
        "description": "aggressive automated run",
        "max_cost_usd": None,
        "max_time_minutes": 240,
        "max_tool_calls": 1800,
    },
}


def _flush() -> None:
    """Persist the active session to ``session.json``."""
    global _last_local_write_mtime
    if _current is None:
        return
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _SESSION_FILE.with_suffix(".json.tmp")
    payload = json.dumps(_current, indent=2, sort_keys=True)
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(_SESSION_FILE)
    try:
        _last_local_write_mtime = _SESSION_FILE.stat().st_mtime
    except OSError:
        _last_local_write_mtime = 0.0


def _reconcile_if_external_write() -> None:
    """Re-load session state when another process updates ``session.json``."""
    global _current, _last_local_write_mtime
    if _SESSION_FILE.exists():
        try:
            mtime = _SESSION_FILE.stat().st_mtime
            if _current is None or mtime > _last_local_write_mtime:
                _current = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
                _last_local_write_mtime = mtime
        except Exception:
            return
        return

    if _last_local_write_mtime > 0:
        _current = None


def _fixed_context_overhead_chars() -> int:
    try:
        from . import limits as _limits

        return _limits._fixed_context_overhead_chars()
    except Exception:
        return 60_000


def _detect_smith_caller() -> dict[str, object] | None:
    """Capture lightweight session-caller identity telemetry."""
    try:
        return {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "hostname": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "localhost",
        }
    except Exception:
        return None


def _persist_smith_caller(caller: dict[str, object] | None) -> None:
    if not caller:
        return
    _SMITH_CALLER_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SMITH_CALLER_FILE.write_text(json.dumps(caller, sort_keys=True, indent=2), encoding="utf-8")


from . import lifecycle  # noqa: E402
from . import limits  # noqa: E402

start = lifecycle.start
complete = lifecycle.complete
load_from_disk = lifecycle.load_from_disk
get = lifecycle.get
note_triage_progress = lifecycle.note_triage_progress
set_triage_requested = lifecycle.set_triage_requested
snapshot_training_bundle = lifecycle.snapshot_training_bundle
stop_pentest_containers = lifecycle.stop_pentest_containers
resolve_launch_contract = lifecycle.resolve_launch_contract
enforce_launch_contract = lifecycle.enforce_launch_contract
enforce_and_execute_launch = lifecycle.enforce_and_execute_launch
policy_launch_plan = lifecycle.policy_launch_plan
evaluate_policy_launch = lifecycle.evaluate_policy_launch

check_limits = limits.check_limits
remaining = limits.remaining
charge_context = limits.charge_context
charge_skill_context = limits.charge_skill_context
reset_context_meter = limits.reset_context_meter
get_context_pressure = limits.get_context_pressure
_stop = limits._stop

__all__ = [
    "start",
    "complete",
    "load_from_disk",
    "get",
    "note_triage_progress",
    "set_triage_requested",
    "snapshot_training_bundle",
    "stop_pentest_containers",
    "resolve_launch_contract",
    "enforce_launch_contract",
    "enforce_and_execute_launch",
    "policy_launch_plan",
    "evaluate_policy_launch",
    "check_limits",
    "remaining",
    "charge_context",
    "charge_skill_context",
    "reset_context_meter",
    "get_context_pressure",
    "_stop",
    "_flush",
    "_fixed_context_overhead_chars",
    "_reconcile_if_external_write",
    "_detect_smith_caller",
    "_persist_smith_caller",
    "_current",
    "_last_local_write_mtime",
    "_SESSION_FILE",
    "_SMITH_CALLER_FILE",
    "PRESETS",
]
