Explicit worker fallback
=======================

Implementation status: ✅ implemented

What this means
- Default path prefers deterministic explicit workers for cost-sensitive roles.
- If explicit worker is unavailable, keep fail-closed behavior.

Current wiring
- `core/policy/agent_backends.py`
  - `choose_backend()` supports explicit-vs-native selection from attestation.
  - `_coerce_explicit_unavailable()` converts explicit-only decision into native + `requires_approval=True` + `fail_closed=True`.
- `core/api_server/routes/policy_routes.py` passes availability flags:
  - `prefer_native` or `explicit_worker_available` in preflight payload.

Next action
- Connect `requires_approval` handling to dashboard/operator gating in a future orchestrator path.
