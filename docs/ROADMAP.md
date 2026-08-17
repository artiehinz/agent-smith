# Roadmap

Agent Smith's goal is to make Codex more effective in real repositories while keeping the runtime small, local, inspectable, and Codex-native. The existing connector, skill, hooks, role definitions, policy layer, SQLite task ledger, and local dashboard are the foundation—not the complete target architecture.

## Current foundation

Implemented today:

- project-local `AGENTS.md`, Codex skill, role definitions, and lifecycle hooks;
- durable project context through `.agent-smith/context.md`;
- direct, structured, and parallel routing with native Codex subagents as the default execution mechanism;
- SQLite-backed policy/task-ledger state and a local HTML dashboard;
- an optional Headroom boundary for operator-managed context compression.

The policy engine and historical documents under `plans/` remain compatibility and design context. They are not a second custom agent runtime and must not become one by default.

## Target architecture

```text
Codex
  ├── native shell, editing, and Git
  ├── native subagents
  ├── AGENTS.md, Skills, and Hooks
  └── Local Control MCP
        ├── repo_search
        ├── repo_read
        ├── tool_search
        ├── tool_read
        └── tool_write
              │
              ▼
        Local daemon
          ├── codebase-memory-mcp
          ├── SQLite + FTS5
          ├── context ranking and cache
          ├── MCP registry/router
          ├── verification evidence
          └── HTML dashboard
```

The control MCP must expose a small, task-relevant surface. Codex continues to own implementation, Git operations, normal tool use, and agent coordination.

## Delivery sequence

### 1. Repository intelligence

- Evaluate and integrate `DeusData/codebase-memory-mcp` as the primary local Tree-sitter code graph.
- Use its symbol, call, and import relationships plus incremental indexing rather than creating a custom parser or graph database.
- Define benchmark repositories and queries before making it a required dependency.

### 2. Retrieval and compact context

- Add a local `repo_search` and `repo_read` layer with progressive expansion: concise skeletons first, then dependency paths and targeted source only when needed.
- Add SQLite + FTS5 for lexical retrieval, capability search, observations, and caches.
- Borrow Aider repo-map ranking ideas—graph relevance, PageRank-like prioritization, and token budgets—without embedding Aider as a runtime dependency.
- Measure retrieval quality, prompt size, latency, and task success against representative repository tasks.

### 3. Minimal MCP broker

- Build a local control MCP backed by a local daemon.
- Start with only `repo_search`, `repo_read`, `tool_search`, `tool_read`, and `tool_write`.
- Keep a registry/router behind those tools so Codex sees only relevant capabilities instead of a large raw MCP catalog.
- Make tool output inspectable and preserve verification evidence, traces, and runtime state locally.

### 4. Reliability and visibility

- Extend the dashboard to show retrieval context, MCP availability, agents, verification evidence, traces, and token use.
- Keep Hooks responsible for context injection, restoration after compaction, task baselines, and proportionate verification/documentation review.
- Prefer native Codex subagents for independent exploration, testing, and review. Use `codex exec` only as an explicit fallback when native routing is unreliable or a fixed model/effort worker is required.

### 5. Evidence-based optional additions

- Use Microsoft SkillOpt offline to improve Codex skills from verified historical runs; do not run it as an online mutation loop.
- Add Docker MCP Gateway only when untrusted MCP isolation is needed.
- Use MCP Inspector to validate and debug the control MCP and integrations.
- Evaluate Serena only if benchmarks show that symbol-aware edits beat Codex's native editing workflow.
- Evaluate Agent Enhancer only if real concurrent workflows need idempotency, locking, or duplicate prevention with opaque IDs.

## Explicit non-goals for the initial runtime

Do not add these before evidence shows they are necessary:

- embeddings or a vector database;
- a custom parser or graph database;
- a custom multi-agent runtime or workflow builder;
- a VS Code extension;
- Docker as a baseline requirement;
- a large always-on MCP tool catalog.

## Success criteria

Each roadmap step should be accepted only when it is local-first, reversible, covered by focused tests, and improves representative Codex tasks without creating more context, tools, or orchestration overhead than it removes.
