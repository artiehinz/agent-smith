# Historical policy follow-through audit

Last reconciled: 2026-08-11

This document replaces an earlier machine-local audit whose absolute Windows links and references to never-created policy documents were not portable. It records only the prototype primitives that still exist. It is not the current Agent Smith setup contract; see the repository `README.md` and tests.

## Retained policy primitives

- Route classification: [`../../core/policy/route_classifier.py`](../../core/policy/route_classifier.py)
- Bounded and delta handoffs: [`../../core/policy/worker_packets.py`](../../core/policy/worker_packets.py)
- Worker lifecycle: [`../../core/policy/worker_lifecycle.py`](../../core/policy/worker_lifecycle.py)
- Executor/tester repair state: [`../../core/policy/executor_tester_repair.py`](../../core/policy/executor_tester_repair.py)
- Single-writer ownership: [`../../core/policy/ownership.py`](../../core/policy/ownership.py)
- Tool batching decisions: [`../../core/policy/tool_batching.py`](../../core/policy/tool_batching.py)
- Legacy launch preflight and model observation: [`../../core/policy/preflight.py`](../../core/policy/preflight.py) and [`../../core/policy/model_attestation.py`](../../core/policy/model_attestation.py)
- Backend selection: [`../../core/policy/agent_backends.py`](../../core/policy/agent_backends.py)
- Token budgets: [`../../core/policy/token_limits.py`](../../core/policy/token_limits.py)
- SQLite task ledger: [`../../core/policy/task_ledger.py`](../../core/policy/task_ledger.py)

## Current integration

The supported Codex wiring now lives in:

- [`../../agent_smith/integration.py`](../../agent_smith/integration.py)
- [`../../agent_smith/templates/agent-smith/SKILL.md`](../../agent_smith/templates/agent-smith/SKILL.md)
- [`../../tests/test_integration.py`](../../tests/test_integration.py)

The detailed files beside this audit are retained as historical design inputs. Their implementation-status statements may be superseded.
