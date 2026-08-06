SQLite task handoff ledger
=========================

Implementation status: ✅ implemented

What this means
- Persist task snapshots and events across process boundaries.
- Keep route/task context and completion events durable.

Current wiring
- `core/policy/task_ledger.py`: SQLite schema + helpers:
  - `upsert_task`
  - `record_task_event`
  - `get_task_ledger`
  - `task_events`
  - `list_open_tasks`
- `core/api_server/routes/policy_routes.py` endpoints:
  - `GET /api/policy/tasks`
  - `GET /api/policy/tasks/{task_id}`
- `core/session/lifecycle.py` emits `route_reset` completion event.
- `_record_policy_completion_event` records terminal completion state.

Next action
- Expose richer filters (status/role/time) in policy tasks UI.
