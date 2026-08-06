"""Lightweight in-memory cost telemetry shim."""

from __future__ import annotations

_STATE = {
    "est_cost_usd": 0.0,
    "tool_calls_total": 0,
}


def reset() -> None:
    """Reset runtime cost counters.

    This is intentionally minimal for local bootstrap compatibility.
    Additional cost accounting providers can wrap this module and keep their own
    persistence layer as long as ``reset`` remains callable.
    """
    _STATE["est_cost_usd"] = 0.0
    _STATE["tool_calls_total"] = 0


def add_cost(amount_usd: float) -> None:
    _STATE["est_cost_usd"] += max(0.0, float(amount_usd))


def increment_calls(count: int = 1) -> None:
    if count > 0:
        _STATE["tool_calls_total"] += int(count)


def snapshot() -> dict[str, float | int]:
    """Return the current in-memory cost summary."""
    return dict(_STATE)
