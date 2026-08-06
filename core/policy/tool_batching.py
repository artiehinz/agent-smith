"""Tool batching helper primitives."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, object] = field(default_factory=dict)
    may_write: bool = False


def batchable_tool_calls(calls: list[ToolCall]) -> list[ToolCall]:
    """Return only calls that are safe to batch together."""
    return [call for call in calls if not call.may_write]


def should_batch_tool_group(calls: list[ToolCall]) -> bool:
    """Whether independent calls should run as one batch."""
    return len(calls) >= 2 and all(not call.may_write for call in calls)


def needs_worker_for_parallel(calls: list[ToolCall], route_hint: str | None) -> bool:
    """Determine if this workload likely needs a parallel-capable launch."""
    normalized = (route_hint or "").strip().lower()
    if len(calls) < 2:
        return False
    if normalized == "direct":
        return False
    if normalized == "structured":
        return len(calls) >= 4 and not should_batch_tool_group(calls)
    if normalized == "parallel":
        return len(calls) >= 3
    return any(call.may_write for call in calls)

