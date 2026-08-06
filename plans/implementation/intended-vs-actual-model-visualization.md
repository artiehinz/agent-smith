Intended vs actual model visualization
=====================================

Implementation status: ✅ implemented (policy UI/API)

What this means
- Surface both intended and actual runtime model/effort per role.
- Show mismatch directly in operator view for delegation trust.

Current wiring
- `core/api_server/routes/policy_routes.py`: `api_run_policy_preflight`, `api_policy_preflight`.
- `core/policy/preflight.py`: preflight prompt parsing/parse state.
- `dashboard/js/policy.js`: renders preflight rows showing `intended` vs `actual`.

Next action
- Expand policy view to include per-scan backend decision status in the same card.
