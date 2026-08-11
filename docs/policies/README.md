# Policy engine documentation

The Python policy engine is an optional compatibility layer behind Agent Smith's native Codex connector. The supported project setup lives in the root `README.md`; executable behavior lives in `core/policy/`, `core/session/`, and `tests/policy/`.

## Current documents

- `task-ledger.md` — SQLite task and evidence records.
- `design-notes/model-actual-vs-intended.md` — intent-versus-observed model design notes.
- `design-notes/model-fallback-runbook.md` — fail-closed fallback behavior.
- `design-notes/route-override-playbook.md` — manual route overrides and handoffs.
- `design-notes/route-reset.md` — one-task route reset behavior.

## Source map

- `core/policy/route_classifier.py` — direct, structured, and parallel routing.
- `core/policy/ownership.py` — single-writer ownership rules.
- `core/policy/preflight.py` and `model_attestation.py` — legacy launch preflight helpers.
- `core/policy/agent_backends.py` — native-versus-explicit backend decisions.
- `core/policy/task_ledger.py` — durable policy events.
- `core/policy/executor_tester_repair.py` — bounded repair-loop state.

Documents under `plans/` are historical planning artifacts and may describe superseded or unimplemented designs.
