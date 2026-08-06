# Plan follow-through audit

Last updated: 2026-08-06 11:36:13

This file tracks the plan-mandated policy additions against current local implementation artifacts.

## Status matrix

1. Automatic Direct / Structured / Parallel route classifier
- Status: implemented
- Evidence:
  - [`core/policy/route_classifier.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/route_classifier.py)
  - [`plans/implementation/route-classifier.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/route-classifier.md)
  - [`docs/policies/execution-routes.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/execution-routes.md)

2. Bounded self-contained worker packets
- Status: implemented
- Evidence:
  - [`core/policy/worker_packets.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/worker_packets.py)
  - [`plans/implementation/bounded-worker-packets.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/bounded-worker-packets.md)

3. Delta-only worker communication
- Status: implemented (policy primitive)
- Evidence:
  - [`core/policy/worker_packets.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/worker_packets.py)
  - [`plans/implementation/delta-only-worker-communication.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/delta-only-worker-communication.md)

4. Evidence-free retry and worker replacement policy
- Status: implemented
- Evidence:
  - [`core/policy/worker_lifecycle.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/worker_lifecycle.py)
  - [`plans/implementation/evidence-free-retry-policy.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/evidence-free-retry-policy.md)

5. Executor-tester repair loop
- Status: implemented
- Evidence:
  - [`core/policy/executor_tester_repair.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/executor_tester_repair.py)
  - [`plans/implementation/executor-tester-repair-loop.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/executor-tester-repair-loop.md)
  - [`docs/policies/repair-loop.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/repair-loop.md)

6. Single-writer ownership enforcement
- Status: implemented
- Evidence:
  - [`core/policy/ownership.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/ownership.py)
  - [`plans/implementation/single-writer-ownership.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/single-writer-ownership.md)
  - [`docs/policies/ownership.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/ownership.md)

7. Tool batching vs. agent-level parallelism
- Status: implemented (policy primitive)
- Evidence:
  - [`core/policy/tool_batching.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/tool_batching.py)
  - [`plans/implementation/tool-batching-before-spawn.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/tool-batching-before-spawn.md)
  - [`docs/policies/worker-strategy.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/worker-strategy.md)

8. Runtime model and reasoning attestation
- Status: implemented
- Evidence:
  - [`core/policy/model_attestation.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/model_attestation.py)
  - [`core/policy/preflight.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/preflight.py)
  - [`plans/implementation/runtime-model-attestation.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/runtime-model-attestation.md)
  - [`docs/policies/model-attestation.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/model-attestation.md)

9. Codex-version build preflight
- Status: implemented (manual trigger)
- Evidence:
  - [`core/policy/preflight.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/preflight.py)
  - [`core/api_server/routes/policy_routes.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/api_server/routes/policy_routes.py)
  - [`plans/implementation/version-preflight.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/version-preflight.md)
  - [`docs/policies/preflight.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/preflight.md)

10. Explicit `codex exec` fallback
- Status: implemented
- Evidence:
  - [`core/policy/agent_backends.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/agent_backends.py)
  - [`plans/implementation/explicit-worker-fallback.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/explicit-worker-fallback.md)
  - [`docs/policies/worker-strategy.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/worker-strategy.md)

11. Intended-versus-actual model visualization
- Status: implemented
- Evidence:
  - [`dashboard/js/policy.js`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/dashboard/js/policy.js)
  - [`core/api_server/routes/policy_routes.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/api_server/routes/policy_routes.py)
  - [`docs/policies/model-attestation.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/model-attestation.md)

12. Per-task and per-agent token ceilings
- Status: implemented
- Evidence:
  - [`core/policy/token_limits.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/token_limits.py)
  - [`plans/implementation/token-limit-policy.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/token-limit-policy.md)
  - [`plans/implementation/token-and-limits.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/plans/implementation/token-and-limits.md)
  - [`docs/policies/token-limits.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/token-limits.md)

13. SQLite handoff ledger
- Status: implemented
- Evidence:
  - [`core/policy/task_ledger.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/task_ledger.py)
  - [`core/policy/__init__.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/core/policy/__init__.py)
  - [`docs/policies/task-ledger.md`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/docs/policies/task-ledger.md)

## Repo bootstrap readiness
- [`tools/bootstrap/policy_repos.ps1`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/tools/bootstrap/policy_repos.ps1) now clones and refreshes all configured reference repos.
- External references checked out:
  - `references/codex_workflow` (origin: `https://github.com/viettran-edgeAI/codex_workflow.git`)
  - `references/codex-agent-config` (origin: `https://github.com/coredo-eu/codex-agent-config.git`)
  - `references/codex_workflows` (origin: `https://github.com/viettran-edgeAI/codex_workflows.git`)

## Structural readiness
- Policy folders and placeholders prepared:
  - `.codex-control/CURRENT_TASK.md`
  - `core/policy/__pending__/events/.gitkeep`
  - `core/policy/__pending__/scripts/.gitkeep`
  - `tools/policy/artifacts/.gitkeep`
  - `tools/policy/tmp/.gitkeep`

## Next gap check
- Completed in this cycle: direct-entry terminal path now records route outcome metadata on completion (`core/session/lifecycle.py`).
  - Evidence:
    - [`tests/policy/test_route_reset_on_complete.py`](/C:/Users/artie/Documents/All_files/Dialog%20Client%20Projects/Random/agent-smith/tests/policy/test_route_reset_on_complete.py)
