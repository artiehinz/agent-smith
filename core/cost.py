"""Compatibility shim for legacy cost telemetry calls.

API-provider token-cost accounting is intentionally disabled in this branch.
This file keeps import compatibility for existing callers while returning
no-op/no-cost values.
"""
from __future__ import annotations


_STATE = {
    "est_cost_usd": 0.0,
    "tool_calls_total": 0,
}


def reset() -> None:
    """Reset legacy counters (no-op)."""
    _STATE["est_cost_usd"] = 0.0
    _STATE["tool_calls_total"] = 0


def add_cost(amount_usd: float) -> None:  # pragma: no cover
    del amount_usd
    # Intentionally left disabled in subscription-only mode.
    return None


def increment_calls(count: int = 1) -> None:
    del count
    # Intentionally left disabled in subscription-only mode.
    return None


def snapshot() -> dict[str, float | int]:
    """Return zeroed legacy cost/call counters."""
    return dict(_STATE)
