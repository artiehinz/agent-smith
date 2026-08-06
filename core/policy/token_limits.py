"""Token budget policy and checking helpers for route/agent execution."""

from __future__ import annotations

from dataclasses import dataclass


class TokenBudgetError(ValueError):
    pass


@dataclass(frozen=True)
class TokenBudget:
    task_hard: int
    task_soft: int
    worker_hard: int
    worker_soft: int

    def enforce(self, used: int, *, worker: bool = False) -> str:
        hard_limit = self.worker_hard if worker else self.task_hard
        soft_limit = self.worker_soft if worker else self.task_soft
        if worker and hard_limit == 0:
            return "ok"
        if used >= hard_limit:
            return "hard_limit"
        if used >= soft_limit:
            return "soft_limit"
        return "ok"


def _validate_positive(value: int, label: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise TokenBudgetError(f"{label} must be non-negative integer")
    return value


def route_token_budget(route: str | None = None) -> TokenBudget:
    """Return default per-route budget envelopes."""

    normalized = (route or "structured").lower()
    if normalized == "direct":
        return TokenBudget(task_hard=8000, task_soft=6400, worker_hard=0, worker_soft=0)
    if normalized == "parallel":
        return TokenBudget(task_hard=60000, task_soft=42000, worker_hard=22000, worker_soft=17000)
    return TokenBudget(task_hard=30000, task_soft=22000, worker_hard=14000, worker_soft=11000)


def clamp_token_budget(
    *,
    route: str | None = None,
    task_hard: int | None = None,
    task_soft: int | None = None,
    worker_hard: int | None = None,
    worker_soft: int | None = None,
) -> TokenBudget:
    base = route_token_budget(route)
    task_hard_v = _validate_positive(task_hard if task_hard is not None else base.task_hard, "task_hard")
    task_soft_v = _validate_positive(task_soft if task_soft is not None else base.task_soft, "task_soft")
    worker_hard_v = _validate_positive(worker_hard if worker_hard is not None else base.worker_hard, "worker_hard")
    worker_soft_v = _validate_positive(worker_soft if worker_soft is not None else base.worker_soft, "worker_soft")
    if task_soft_v > task_hard_v:
        raise TokenBudgetError("task_soft cannot exceed task_hard")
    if worker_soft_v > worker_hard_v and base.worker_hard != 0:
        raise TokenBudgetError("worker_soft cannot exceed worker_hard")
    return TokenBudget(task_hard=task_hard_v, task_soft=task_soft_v, worker_hard=worker_hard_v, worker_soft=worker_soft_v)
