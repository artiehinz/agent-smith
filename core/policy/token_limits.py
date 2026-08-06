"""Token budgets for execution routes."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenBudget:
    task_hard: int
    task_soft: int
    worker_hard: int
    worker_soft: int


_ROUTE_TOKEN_LIMITS: dict[str, TokenBudget] = {
    "direct": TokenBudget(task_hard=12000, task_soft=9000, worker_hard=4500, worker_soft=3200),
    "structured": TokenBudget(task_hard=24000, task_soft=18000, worker_hard=8000, worker_soft=6000),
    "parallel": TokenBudget(task_hard=36000, task_soft=26000, worker_hard=12000, worker_soft=9000),
}


def route_token_budget(route: str | None) -> TokenBudget:
    """Return the route budget used by policy telemetry and policy blobs."""
    normalized = (route or "").strip().lower()
    return _ROUTE_TOKEN_LIMITS.get(normalized, _ROUTE_TOKEN_LIMITS["direct"])


def clamp_token_budget(
    token_count: int | None,
    *,
    route: str | None = None,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    """Clamp token count to route defaults and caller-provided bounds."""
    if token_count is None:
        return minimum
    value = int(token_count)
    if value < minimum:
        value = minimum

    route_cap = route_token_budget(route).task_hard
    if maximum is None or maximum <= 0:
        maximum = route_cap
    return min(value, max(minimum, maximum))

