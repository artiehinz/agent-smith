"""Tests for session-start policy helpers."""

from mcp_server.session_tools.start import (
    _safe_route_hint,
    _coerce_non_negative,
    _build_route_policy,
    _route_context_from_options,
)


def test_safe_route_hint_accepts_only_known_routes():
    assert _safe_route_hint("direct") == "direct"
    assert _safe_route_hint("PARALLEL") == "parallel"
    assert _safe_route_hint("none") is None
    assert _safe_route_hint(12) is None


def test_numeric_policy_values_coerce_negative_and_large():
    assert _coerce_non_negative("3", 4) == 3
    assert _coerce_non_negative(-2, 4) == 4
    assert _coerce_non_negative("99", 4) == 10
    assert _coerce_non_negative("bad", 4) == 4


def test_route_context_from_options_and_policy_build_honor_route_hint():
    context = _route_context_from_options("standard", {"policy_task_breadth": 6, "scope": []}, "https://example.com")
    assert context.task_breadth == 6
    assert context.affected_packages == 0

    policy = _build_route_policy(
        depth="standard",
        opts={"route": "parallel"},
        target="https://example.com",
    )
    assert policy["route"] == "parallel"
    assert policy["override_applied"] is True
    assert policy["policy_engine"] == "route_classifier_v1"
