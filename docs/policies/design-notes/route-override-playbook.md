Route override playbook
=====================

Entry points
- `POST /api/policy/route` with `{ "route": "direct|structured|parallel" }`.
- Session start option: `scan` route hint via `_build_route_policy` in `mcp_server/session_tools/start.py`.

Behavior
- User override sets `policy.route`, `policy.route_hint`, `policy.override_applied=true`.
- Completion lifecycle (`complete`) calls route reset:
  - clears `route_hint`
  - sets `override_applied=false`
  - restores classifier-derived route.
- Dashboard route control in `dashboard/tabs/policy.html` and `dashboard/js/policy.js`.

Guardrail
- Route reset is persisted in policy task ledger (`route_reset` event) for auditability.
