# Policy: Task ledger

## Purpose

Keep compact, queryable execution evidence in SQLite instead of many loose markdown state files.

## Tables

- `task_ledger` stores current task state (id, route, owner role, status, metadata).
- `task_events` stores per-task status transitions, packet snapshots, and evidence notes.

## Lifecycle fields

- status: `open`, `in_progress`, `blocked`, `completed`, `failed`
- metadata: JSON with route, limits, attestation results, ownership map

## Output rule

UI and logs should derive from this ledger; optional reports can be generated from it but should not be treated as source of truth.
