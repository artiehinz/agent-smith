Evidence-free retry and replacement
===========================

Implementation status: ✅ implemented

What this means
- Detect non-evidentiary replies and force a compact corrective message.
- Escalate to replacement worker after repeated evidence-free responses.

Current wiring
- `core/policy/worker_lifecycle.py`
  - `has_evidence(message)` supports:
    - dict markers (`changed_files`, `commands`, `result`, `test_failure`, etc.)
    - string markers (`ran`, path-like tokens, keyword combos)
  - `evaluate_worker_response()` returns:
    - `RETRY` on first empty turn
    - `REPLACE` on second evidence-free turn
    - `ESCALATE` if replacement also fails to show evidence

Next action
- Hook this lifecycle into worker runner callback path so retries/replacements are actionable.
