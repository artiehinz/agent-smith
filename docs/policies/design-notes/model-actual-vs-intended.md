Model intended vs actual policy note
==================================

Goal
- Track intended model/effort alongside runtime-observed values for every policy-targeted role.

Current evidence path
- `core/policy/preflight.py`: parse role/model/effort/sandbox.
- `core/policy/model_attestation.py`: `ModelAttestation` + `attestation_report`.
- `core/api_server/routes/policy_routes.py`: stores both `preflight` and backend decision blobs in session policy.
- `dashboard/js/policy.js`: renders mismatch status and values.

Operational posture
- `match` -> proceed with native when not cost-sensitive risk.
- `mismatch`/`missing_actual` -> prefer explicit/strict backend and enforce fail-closed where configured.
