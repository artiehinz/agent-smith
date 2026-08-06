Model fallback runbook
=====================

When attestation indicates non-match:
1) Record `status` and evidence in session policy.
2) Record backend decision (native vs explicit + fail_closed).
3) If explicit not available:
   - keep execution on native
   - set `requires_approval` and `fail_closed`
4) Surface in dashboard `policy` tab and `route` task ledger event stream.

Code anchors
- `core/policy/agent_backends.py::_coerce_explicit_unavailable`
- `core/policy/model_attestation.py`
- `core/api_server/routes/policy_routes.py`
- `dashboard/js/policy.js`
