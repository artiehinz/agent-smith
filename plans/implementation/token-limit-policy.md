Token limit policy
=================

Implementation status: ✅ implemented

What this means
- Per-route token envelopes for task and workers.
- Soft/hard enforcement points in policy tooling.

Current wiring
- `core/policy/token_limits.py`
  - `TokenBudget` and `TokenBudgetError`
- `route_token_budget(route)` defaults:
  - `direct`: lower task budget, no worker budget
  - `structured`: medium budget
  - `parallel`: highest budget
- `clamp_token_budget(...)` for bounded updates.
- Session policy stores `token_budget` under `session["policy"]`.

Next action
- Hook `enforce()` checks into active worker execution loops and route switches.
