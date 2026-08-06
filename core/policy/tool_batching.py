"""Tool-call batching versus extra worker spawn policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: dict
    may_write: bool = False


def independent_reads(calls: list[ToolCall]) -> bool:
    """True when all calls are reads and can be batched inside one agent."""
    if not calls:
        return False
    return all(not call.may_write for call in calls) and len(calls) >= 2


def needs_worker_for_parallel(calls: list[ToolCall], route_hint: str = "direct") -> bool:
    """Conservative rule used before launching extra workers."""
    if route_hint == "parallel":
        return True
    if independent_reads(calls):
        return False
    return False
