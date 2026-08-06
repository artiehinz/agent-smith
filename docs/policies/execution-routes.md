## Execution routes

The policy uses three routes:

- `direct`: one Codex owner, minimal process, exact-file changes.
- `structured`: one owner with planning + verification loop.
- `parallel`: orchestrator plus bounded workers for independent work.

### Classifier inputs

- `task_breadth`
- `affected_packages`
- `uncertainty`
- `verification_complexity`
- `independent_work_opportunities`
- `estimated_agent_overhead`

### Route selection

- The route is re-evaluated per task and should be reset when the task finishes.
- Explicit user override is supported: `route: direct`, `route: structured`, `route: parallel`.
- The classifier returns a score and rationale for auditability.

### Runtime knobs (session start)

- `route` or `route_hint` (`direct|structured|parallel`)
- `policy_task_breadth` (integer)
- `policy_affected_packages` (integer)
- `policy_uncertainty` (integer)
- `policy_verification_complexity` (integer)
- `policy_independent_work_opportunities` (integer)
- `policy_estimated_agent_overhead` (integer)
