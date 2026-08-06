"""Tests for route token limits."""

from core.policy.token_limits import TokenBudgetError, route_token_budget, clamp_token_budget


def test_default_limits_by_route():
    direct = route_token_budget("direct")
    structured = route_token_budget("structured")
    parallel = route_token_budget("parallel")

    assert direct.task_hard == 8000
    assert structured.task_hard == 30000
    assert parallel.task_hard > structured.task_hard


def test_clamp_token_limits_preserves_order():
    budget = clamp_token_budget(route="parallel", task_soft=30000, task_hard=50000)
    assert budget.task_soft == 30000
    assert budget.task_hard == 50000


def test_invalid_token_order_errors():
    try:
        clamp_token_budget(route="structured", task_hard=1000, task_soft=2000)
    except TokenBudgetError:
        assert True
    else:
        assert False
