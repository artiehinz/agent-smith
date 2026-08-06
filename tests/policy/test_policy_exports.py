"""Smoke tests for policy package exports."""

from core import policy


def test_policy_exports_core_modules():
    assert hasattr(policy, "Route")
    assert hasattr(policy, "RouteContext")
    assert hasattr(policy, "classify_route")
    assert hasattr(policy, "ToolCall")
    assert hasattr(policy, "OwnershipLedger")
    assert hasattr(policy, "should_run_context_scout")
