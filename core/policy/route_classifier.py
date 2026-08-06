"""Route classifier for execution strategy.

The execution routes are:
    - direct: one Codex owner, minimal process and no delegation
    - structured: one owner with explicit planning/verification
    - parallel: orchestrator + bounded workers for genuinely independent work

The policy is intentionally lightweight and local. It is designed to be tuned by
config and metrics; by default it mirrors the score terms requested in the plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Route(str, Enum):
    """Supported execution routes."""

    DIRECT = "direct"
    STRUCTURED = "structured"
    PARALLEL = "parallel"


_KNOWN_OVERRIDE = {value.value: value for value in Route}


@dataclass(frozen=True)
class RouteContext:
    """Inputs used to pick an execution route.

    All fields are expected to be non-negative integers in 0..10 but callers may
    pass larger values. The classifier normalises by clamping to that range to
    avoid skew from noisy telemetry.
    """

    task_breadth: int = 0
    affected_packages: int = 0
    uncertainty: int = 0
    verification_complexity: int = 0
    independent_work_opportunities: int = 0
    estimated_agent_overhead: int = 0
    route_hint: str | None = None


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    score: float
    rationale: list[str]
    override_applied: bool = False
    details: dict[str, int] = field(default_factory=dict)


_WEIGHTS = {
    "task_breadth": 1.0,
    "affected_packages": 1.2,
    "uncertainty": 1.3,
    "verification_complexity": 1.3,
    "independent_work_opportunities": 1.1,
    # Higher overhead usually reduces the ROI of delegation, so subtract it.
    "estimated_agent_overhead": -0.8,
}

# Empirical defaults: direct for mostly routine tasks, structured for normal
# implementation work, parallel when complexity and independence combine.
_THRESHOLDS = {
    Route.DIRECT: 0.0,
    Route.STRUCTURED: 6.5,
    Route.PARALLEL: 11.5,
}


def _clamp(v: int) -> int:
    """Clamp numeric inputs to 0..10 where 0 means absent and 10 means high."""

    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    if n < 0:
        return 0
    if n > 10:
        return 10
    return n


def _score(context: RouteContext) -> tuple[float, dict[str, int], list[str]]:
    values = {
        "task_breadth": _clamp(context.task_breadth),
        "affected_packages": _clamp(context.affected_packages),
        "uncertainty": _clamp(context.uncertainty),
        "verification_complexity": _clamp(context.verification_complexity),
        "independent_work_opportunities": _clamp(context.independent_work_opportunities),
        "estimated_agent_overhead": _clamp(context.estimated_agent_overhead),
    }
    rationale = []
    total = 0.0
    for key, weight in _WEIGHTS.items():
        contribution = values[key] * weight
        total += contribution
        sign = "+" if contribution >= 0 else "-"
        rationale.append(f"{key}={values[key]} {sign}{abs(contribution):.1f}")
    return total, values, rationale


def _route_from_score(score: float) -> Route:
    if score >= _THRESHOLDS[Route.PARALLEL]:
        return Route.PARALLEL
    if score >= _THRESHOLDS[Route.STRUCTURED]:
        return Route.STRUCTURED
    return Route.DIRECT


def _parse_route_hint(route_hint: str | None) -> Route | None:
    if not route_hint:
        return None
    cleaned = route_hint.strip().lower()
    return _KNOWN_OVERRIDE.get(cleaned)


def classify_route(context: RouteContext | dict[str, Any]) -> RouteDecision:
    """Classify one context into a route.

    ``context`` can be a RouteContext instance or a mapping with the same fields.
    """
    if isinstance(context, dict):
        normalized = RouteContext(
            task_breadth=context.get("task_breadth", 0),
            affected_packages=context.get("affected_packages", 0),
            uncertainty=context.get("uncertainty", 0),
            verification_complexity=context.get("verification_complexity", 0),
            independent_work_opportunities=context.get("independent_work_opportunities", 0),
            estimated_agent_overhead=context.get("estimated_agent_overhead", 0),
            route_hint=context.get("route_hint"),
        )
    elif isinstance(context, RouteContext):
        normalized = context
    else:
        raise TypeError("context must be RouteContext or a mapping with known fields")

    hint = _parse_route_hint(normalized.route_hint)
    score, details, rationale = _score(normalized)
    if hint is not None:
        return RouteDecision(
            route=hint,
            score=score,
            rationale=[f"Explicit override: route={hint.value}"] + rationale,
            override_applied=True,
            details=details,
        )

    return RouteDecision(
        route=_route_from_score(score),
        score=score,
        rationale=rationale,
        override_applied=False,
        details=details,
    )
