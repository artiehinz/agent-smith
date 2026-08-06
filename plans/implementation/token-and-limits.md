## Token and Limits Policy

Token ceilings and budget policy
===============================

Implementation status: implemented

What this means
- Every route/agent has explicit token ceilings.
- Session and worker policy uses these ceilings as guardrails for bounded execution.
- Limits can be tuned by role/routing policy instead of hardcoded assumptions.

Current wiring
- `core/policy/token_limits.py` defines role and route budgets, plus policy lookup helpers.
- `core/policy/route_classifier.py` attaches token budgets to route decisions.
- `core/policy/task_ledger.py` stores budget decisions per task/event.
- Dashboard rendering in `dashboard/js/policy.js` can display token-policy state.

Next action
- Add route-specific burn-rate observability before introducing adaptive budget reduction.
