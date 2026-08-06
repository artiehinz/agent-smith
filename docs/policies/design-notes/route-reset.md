# Route Reset Design Note
Status: implemented

Why
- Routes are not meant to persist between unrelated tasks.
- A route assigned during one session turn should not bias the next turn.

Current behavior
- On task completion, `core/session/lifecycle.py` calls `_reset_policy_on_completion`.
- The policy engine restores the baseline route and removes the session `route_hint`.
- A `route_reset` event is recorded in the task ledger for traceability.

Evidence fields
- `previous_route`
- `previous_route_hint`
- `route`
- `scope`
- `notes` (`"policy route reset after task completion"`)

Completion event also now includes:
- `route` (route in force at terminal transition)
- `route_hint`
- `route_reset_applied`
- `route_after_reset`
- `route_reset_source`

Open question
- Whether to additionally reset route-derived confidence scores when completion events are manual or partial.
