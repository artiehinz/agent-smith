Delta-only worker communication
==============================

Implementation status: ✅ implemented (contract)

What this means
- Follow-up messages to workers should carry only changed fields.
- Reduces token waste and noisy context growth.

Current wiring
- `core/policy/worker_packets.py:as_delta_message(base, update)` returns only changed keys.
- API/preflight and policy payload helpers support compact map updates instead of re-sending full state.

Next action
- Apply `as_delta_message` at the first delegated-worker follow-up call site (once worker runner is connected).
