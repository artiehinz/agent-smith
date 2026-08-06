Runtime model attestation
=======================

Implementation status: ✅ implemented

What this means
- Run a runtime preflight probe to capture actual model/effort/sandbox.
- Treat missing/mismatched evidence as non-match/fail-closed when required.

Current wiring
- `core/policy/preflight.py`
  - `PreflightIntent`, `PreflightResult`
  - `generate_preflight_marker()`, `preflight_prompt()`, `parse_preflight_output()`
- `core/api_server/routes/policy_routes.py`:
  - `POST /api/policy/preflight`
  - stores `preflight` + `backend_decisions` in session policy
- `core/policy/model_attestation.py` maps intended/actual and `status` values.

Next action
- Replace manual marker paste with runnable local probe command path in non-manual workflows.
