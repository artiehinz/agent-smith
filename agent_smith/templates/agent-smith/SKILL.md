---
name: agent-smith
description: Route, coordinate, and verify Codex repository work with the smallest effective multi-agent topology. Use for non-trivial implementation, debugging, refactoring, review, migration, or repository-wide tasks where decomposition, parallel discovery, isolated execution, or independent verification may improve correctness or elapsed time.
---

# Agent Smith

Own the outcome in the primary thread. Use agents only when their handoff costs less than the time or uncertainty they remove.

## Route the task

Choose one route before implementation:

- `direct`: one clear owner, tightly coupled edits, or delegation overhead dominates.
- `structured`: one primary writer plus bounded read-only discovery or independent verification.
- `parallel`: two or more genuinely independent work packages with isolated ownership and a clear integration owner.

Do not infer that a large task needs many agents. Do not parallelize overlapping writes in one worktree.

## Define acceptance

State the observable result and proportionate verification before editing. Identify public contracts, data-loss or security risks, and unrelated dirty-worktree changes that must be preserved.

## Delegate bounded packets

Give each agent only:

- outcome and observable `Done when`;
- ownership boundary and non-goals;
- authoritative files or facts;
- required handoff: changed paths or source evidence, commands and results, risks, and uncertainty.

Use the installed `agent_smith_explorer`, `agent_smith_executor`, `agent_smith_tester`, and `agent_smith_reviewer` roles when they fit. Keep architecture decisions, conflict resolution, integration, commits, pushes, and the final verdict in the primary thread.

## Integrate and verify

Inspect every handoff against the current worktree. Run focused checks first, then broader affected tests when regression risk warrants them. A worker's success claim is evidence, never the final verdict.

For detailed routing signals, ownership rules, and handoff examples, read [references/policy.md](references/policy.md).
