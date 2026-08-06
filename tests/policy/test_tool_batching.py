"""Tests for lightweight batching-vs-worker policy."""

from core.policy.tool_batching import ToolCall, independent_reads, needs_worker_for_parallel


def test_independent_reads_needs_two_readonly_calls():
    assert independent_reads([]) is False
    assert independent_reads([ToolCall(tool="a", args={})]) is False
    assert independent_reads([
        ToolCall(tool="a", args={}),
        ToolCall(tool="b", args={}, may_write=False),
    ]) is True
    assert independent_reads([
        ToolCall(tool="a", args={}),
        ToolCall(tool="b", args={}, may_write=True),
    ]) is False


def test_parallel_route_prefers_workers():
    calls = [ToolCall(tool="a", args={}), ToolCall(tool="b", args={})]
    assert needs_worker_for_parallel(calls, route_hint="parallel") is True
    assert needs_worker_for_parallel(calls, route_hint="direct") is False


def test_non_parallel_mixed_calls_stays_in_agent():
    calls = [
        ToolCall(tool="a", args={}, may_write=True),
        ToolCall(tool="b", args={}, may_write=True),
    ]
    assert needs_worker_for_parallel(calls, route_hint="structured") is False
