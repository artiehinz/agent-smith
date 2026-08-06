Bounded worker packets
======================

Implementation status: ✅ implemented

What this means
- Provide small, bounded worker task capsules and explicit read/write scopes.
- Keep packet contents compact so delegation stays controlled.

Current wiring
- `core/policy/worker_packets.py`
  - `PacketScope`: `read`, `write`, `protected`
  - `WorkerPacket`: `task_id`, `role`, `outcome`, `scope`, `acceptance`, `context_refs`, `return_fields`
  - `as_delta_message()` for follow-up delta-only updates
  - `clamp_token_budget()` for packet token caps
- No auto-generated giant payloads; packets are explicit serializable objects for worker handoff.

Next action
- Use these packet fields in delegated worker launch paths once worker orchestration is implemented.
