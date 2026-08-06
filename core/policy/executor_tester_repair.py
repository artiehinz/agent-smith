"""Executor/tester repair loop policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DefectType(str, Enum):
    PRODUCTION = "production"
    TEST_FIXTURE = "test_fixture"
    TEST_STABILITY = "test_stability"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class RepairLoopState:
    defect_type: DefectType
    cycles: int = 0
    max_cycles: int = 2

    def exceeds_budget(self) -> bool:
        return self.cycles >= self.max_cycles


def defect_destination(defect_type: str) -> str:
    """Return the most appropriate recipient for a defect."""
    normalized = (defect_type or "").lower().strip()
    if normalized in {"production", "runtime", "runtime_regression", "functional"}:
        return "executor"
    if normalized in {"fixture", "test", "unit", "integration", "e2e"}:
        return "tester"
    return "orchestrator"


def should_continue_repair(loop: RepairLoopState) -> bool:
    """True while another repair loop is still allowed and useful."""
    return not loop.exceeds_budget()


def cycle_once(loop: RepairLoopState) -> RepairLoopState:
    """Advance one repair loop."""
    return RepairLoopState(defect_type=loop.defect_type, cycles=loop.cycles + 1, max_cycles=loop.max_cycles)
