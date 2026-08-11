---
name: agent-smith
description: Maintain project context, review documentation impact, and route Codex repository work with the smallest effective topology. Use for every repository modification; keep small changes direct, and use structured or parallel agents only when decomposition, independent discovery, isolated execution, or verification materially improves the outcome.
---

# Agent Smith

Own the outcome in the primary thread. Use agents only when their handoff costs less than the time or uncertainty they remove.

## Load project memory

Read `.agent-smith/context.md` before non-trivial work, then inspect the relevant source, tests, and project documentation. Treat source, tests, and explicit user instructions as authoritative if the context is stale. Keep the context compact: durable facts and decisions belong there; task logs, timestamps, speculative notes, and information cheaply rediscovered from one file do not.

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

## Review the documentation delta

Before finishing any material repository change, decide whether it changed behavior, architecture, setup, canonical commands, invariants, operational constraints, or a durable decision.

- If yes, update `.agent-smith/context.md` and the smallest relevant project documentation in the same change.
- If no, do not edit documentation merely to record activity; explicitly confirm the review found no durable documentation delta.
- Keep context below 200 lines and 16 KiB. Remove superseded detail instead of allowing it to grow indefinitely.
- Do not let context claims override verified code or tests.

For detailed routing signals, ownership rules, and handoff examples, read [references/policy.md](references/policy.md).
