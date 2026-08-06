Executor-tester repair loop
==========================

Implementation status: ✅ implemented (policy model)

What this means
- Production defects return to executor.
- Test defects should return to tester.
- Repair cycles are bounded with escalation after repeated loops.

Current wiring
- `core/policy/executor_tester_repair.py`
  - `defect_destination()` maps defect kinds.
  - `RepairLoopState` tracks `cycle` and `max_cycles=2`.
  - `should_continue_repair()` + `cycle_once()` enforce loop budget.

Next action
- Integrate this policy with actual orchestrator loop when worker orchestration is complete.
