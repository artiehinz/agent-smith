# Reusable Codex multi-agent team prompt

Use the current Sol model only as the main lead/orchestrator for planning, architecture, task decomposition, difficult reasoning, delegation, and final synthesis.

Create or use these local Codex agents under `~/.codex/agents/`:

- `coder`: `gpt-5.6-luna`, reasoning `xhigh`. Primary execution agent. After Sol creates the plan, coder owns the task end-to-end: inspect and research the repository, understand existing patterns, implement, fix, refactor, run tests, debug failures, and verify the final result.
- `researcher`: `gpt-5.6-luna`, reasoning `xhigh`. Use mainly for research-only tasks where no implementation is required.
- `browser_debugger`: `gpt-5.6-luna`, reasoning `xhigh`. Optional browser/runtime specialist. Reproduce UI problems and collect screenshots, console, DOM, and network evidence. Must not edit application code.
- `reviewer`: `gpt-5.6-terra`, reasoning `high`. Optional independent reviewer for complex, risky, security-sensitive, or regression-prone changes.

For `browser_debugger`, use:

```toml
[mcp_servers.chrome_devtools]
url = "http://localhost:3000/mcp"
startup_timeout_sec = 20
```

## Core workflow

For implementation, fix, refactor, or test tasks:

`User request → Sol plans → Sol delegates the complete plan to one coder → coder investigates, implements, tests, debugs, verifies, and reports → Sol synthesizes and responds.`

The coder receives the goal, constraints, plan, relevant context, and success criteria, then owns execution without routine micromanagement.

Do not automatically split normal implementation work into researcher, coder, and reviewer stages. The coder is responsible for repository investigation, implementation, refactoring, tests, debugging, and verification.

Use `researcher` only for research or analysis without implementation, or when Sol explicitly decides a separate research lane is genuinely beneficial. Use `reviewer` only when an independent second opinion materially improves confidence. Use `browser_debugger` only when browser/runtime evidence is genuinely needed. Use multiple or parallel subagents only for genuinely independent workstreams.

## Strict model and context policy

- Sol is exclusively reserved for the main/root agent.
- Never spawn Sol as a subagent without explicit user approval for that specific task.
- No generic, temporary, dynamic, named, or ad-hoc subagent may inherit Sol automatically.
- Default unspecified or ad-hoc subagents to `gpt-5.6-luna`.
- Configure `fork_turns = "none"` at the supported scope.
- Subagents must not automatically inherit the parent conversation.
- Sol must explicitly pass the coder the implementation plan, task goal, constraints, relevant context, and success criteria.

## Sol responsibilities

Sol should understand the request, inspect enough context to plan correctly, make architectural decisions, create the implementation plan, define success criteria and constraints, delegate execution, resolve genuine blockers, and synthesize the final result.

Sol should not normally write the implementation, perform routine repository research, run the normal test/debug loop, or spawn multiple agents for work one coder can reasonably complete.

## Reuse guidance

Before applying this prompt to another project, inspect that project's existing `~/.codex/config.toml`, `~/.codex/agents/`, and `AGENTS.md`. Preserve unrelated settings and agents, and adapt keys to the installed Codex version. Validate the resulting TOML and verify agent recognition where possible.
