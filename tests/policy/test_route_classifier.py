"""Tests for route classification policy."""

from core.policy import Route, RouteContext, classify_route


def test_explicit_override_is_honored():
    ctx = RouteContext(task_breadth=0, route_hint="parallel")
    decision = classify_route(ctx)
    assert decision.route == Route.PARALLEL
    assert decision.override_applied is True


def test_direct_to_parallel_scaling():
    low = RouteContext(
        task_breadth=1,
        affected_packages=0,
        uncertainty=1,
        verification_complexity=1,
        independent_work_opportunities=0,
        estimated_agent_overhead=1,
    )
    high = RouteContext(
        task_breadth=8,
        affected_packages=6,
        uncertainty=7,
        verification_complexity=8,
        independent_work_opportunities=6,
        estimated_agent_overhead=2,
    )
    assert classify_route(low).route.value in {"direct", "structured"}
    assert classify_route(high).route == Route.PARALLEL
