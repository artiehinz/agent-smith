"""Executor/tester repair loop policy helpers."""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class RepairLoopState:
    cycle: int = 0
    max_cycles: int = 2


def defect_destination(defect: str) -> str:
    text = (defect or "").strip().lower()
    if not text:
        return "orchestrator"
    if any(token in text for token in ("production", "p0", "critical", "runtime", "repro")):
        return "executor"
    if any(token in text for token in ("test", "fixture", "lint", "unit", "integration", "ci")):
        return "tester"
    return "orchestrator"


def should_continue_repair(state: RepairLoopState) -> bool:
    return state.cycle < state.max_cycles


def cycle_once(state: RepairLoopState) -> RepairLoopState:
    return replace(state, cycle=state.cycle + 1)

