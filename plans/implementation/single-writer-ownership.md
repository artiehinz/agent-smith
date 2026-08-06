Single-writer ownership
======================

Implementation status: ✅ implemented (module contract)

What this means
- One writer per scope to avoid concurrent file-write conflicts.
- Ownership checks are local and conflict-aware.

Current wiring
- `core/policy/ownership.py`
  - `OwnershipLedger` with `acquire`, `release`, `can_edit`, `owner_of`.

Next action
- Enforce ownership in the worker-launch queue path before dispatching file-writing tasks.
