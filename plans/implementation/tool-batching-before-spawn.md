Tool batching before spawn
========================

Implementation status: ✅ implemented

What this means
- Prefer local batching of independent reads before launching extra workers.
- Keep workers for true parallelizable independent work.

Current wiring
- `core/policy/tool_batching.py`
  - `ToolCall` descriptor with `may_write` flag
  - `independent_reads(calls)` detects pure-read batching opportunity
  - `needs_worker_for_parallel(calls, route_hint)` as coarse gate

Next action
- Feed real tool-call batches from runner telemetry into this gate before worker spawn decisions.
