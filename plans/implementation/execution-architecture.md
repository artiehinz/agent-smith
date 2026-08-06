## Execution Architecture Policy

Execution architecture
=====================

Implementation status: implemented

What this means
- Task execution still follows the local daemon + policy layer + bounded helpers architecture.
- New policy layer controls route selection, route reset, model attestation, and fallback behavior before worker launch.
- Delegation remains bounded and compact:
  - one main owner by default
  - worker packets
  - explicit evidentiary requirements
  - executor/tester repair loop

Current wiring
- `mcp_server/session_tools/start.py` carries policy into the active session snapshot.
- `core/session/lifecycle.py` resets route state after task completion so later prompts start clean.
- `core/policy/agent_backends.py` selects native vs explicit worker execution path.
- `core/policy/preflight.py` and `core/policy/model_attestation.py` provide runtime verification and hardening.
- `core/policy/worker_lifecycle.py` enforces evidence-based replacement rules.
- `core/policy/executor_tester_repair.py` defines the executor/tester repair policy.

Status
- Direct-route terminal transition now records route state in completion telemetry (`core/session/lifecycle.py`), including route outcome fields.
