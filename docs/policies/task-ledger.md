# Policy: Task ledger

## Purpose

Keep compact, queryable execution evidence in SQLite instead of many loose markdown state files.

## Tables

- `task_ledger` stores current task state (id, route, owner role, status, metadata).
- `task_events` stores per-task status transitions, packet snapshots, and evidence notes.

## Completed-event payload (policy session terminal states)

- `status`: terminal status (`complete`, `incomplete_with_unresolved_blockers`, `limit_reached`)
- `notes`: completion notes
- `route`: route at terminal transition
- `route_hint`: user/system hint driving the terminal run
- `route_reset_applied`: whether route was reset for next task
- `route_after_reset`: route value after reset
- `route_reset_source`: `"completion"` or `"limit_reached"`
- `stop_reason`: optional limit/hard-stop reason
- `quality_gate`: optional quality gate marker

## Lifecycle fields

- status: `open`, `in_progress`, `blocked`, `completed`, `failed`
- metadata: JSON with route, limits, attestation results, ownership map

## Output rule

UI and logs should derive from this ledger; optional reports can be generated from it but should not be treated as source of truth.
