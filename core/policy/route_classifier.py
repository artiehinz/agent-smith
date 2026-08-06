"""Route classifier policy primitives.

This module converts task-level signals into one of three execution routes:
``direct``, ``structured`` or ``parallel``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RouteChoice(str, Enum):
    """Supported execution routes."""

    DIRECT = "direct"
    STRUCTURED = "structured"
    PARALLEL = "parallel"


@dataclass(frozen=True)
class RouteContext:
    task_breadth: int
    affected_packages: int
    uncertainty: int
    verification_complexity: int
    independent_work_opportunities: int
    estimated_agent_overhead: int
    route_hint: str | None = None


@dataclass(frozen=True)
class RouteDecision:
    route: RouteChoice
    score: float
    rationale: list[str]
    details: dict[str, int | float]
    override_applied: bool = False
    route_hint: str | None = None


RouteClassification = RouteDecision


def _to_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def classify_route(context: RouteContext) -> RouteDecision:
    """Classify route intent from context signals.

    The model is intentionally light-weight and deterministic so policy decisions
    stay explainable and stable in production.
    """
    details = {
        "task_breadth": _to_int(context.task_breadth),
        "affected_packages": _to_int(context.affected_packages),
        "uncertainty": _to_int(context.uncertainty),
        "verification_complexity": _to_int(context.verification_complexity),
        "independent_work_opportunities": _to_int(context.independent_work_opportunities),
        "estimated_agent_overhead": _to_int(context.estimated_agent_overhead),
    }
    hint = (context.route_hint or "").strip().lower()
    rationale: list[str] = []

    if hint in {choice.value for choice in RouteChoice}:
        rationale.append(f"route_hint={hint}")
        return RouteDecision(
            route=RouteChoice(hint),
            score=0.0,
            rationale=rationale,
            details=details,
            override_applied=True,
            route_hint=hint,
        )

    score = (
        1.2 * details["task_breadth"]
        + 1.0 * details["affected_packages"]
        + 0.8 * details["uncertainty"]
        + 1.1 * details["verification_complexity"]
        + 1.0 * details["independent_work_opportunities"]
        + 0.7 * details["estimated_agent_overhead"]
    )

    if score <= 9:
        route = RouteChoice.DIRECT
        rationale.append("low-breadth or low-parallel potential")
    elif score <= 16:
        route = RouteChoice.STRUCTURED
        rationale.append("moderate complexity with bounded orchestration")
    else:
        route = RouteChoice.PARALLEL
        rationale.append("high uncertainty and multi-dimensional work")

    return RouteDecision(
        route=route,
        score=round(float(score), 2),
        rationale=rationale,
        details=details,
        override_applied=False,
        route_hint=None,
    )

