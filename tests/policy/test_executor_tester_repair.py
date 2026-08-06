"""Tests for executor-tester repair loop policy."""

from core.policy.executor_tester_repair import (
    DefectType,
    RepairLoopState,
    cycle_once,
    defect_destination,
    should_continue_repair,
)


def test_defect_destination_targets_expected_owner():
    assert defect_destination("production") == "executor"
    assert defect_destination("test") == "tester"
    assert defect_destination("mystery_case") == "orchestrator"


def test_repair_loop_cycle_budget():
    loop = RepairLoopState(defect_type=DefectType.PRODUCTION, cycles=0, max_cycles=2)
    assert loop.exceeds_budget() is False
    assert should_continue_repair(loop) is True

    loop = cycle_once(loop)
    assert loop.cycles == 1
    assert should_continue_repair(loop) is True

    loop = cycle_once(loop)
    assert loop.exceeds_budget() is True
    assert should_continue_repair(loop) is False
