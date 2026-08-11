# Agent Smith

Agent Smith is a repo-local orchestration layer for Codex. It connects durable project guidance, a reusable workflow skill, namespaced subagent roles, an optional policy engine, and a local dashboard without replacing a project's existing instructions.

The repository is currently **alpha**. The Codex connector and doctor workflow are the supported integration path; the older scan/session API remains available for compatibility.

## What a connection installs

Running `connect` adds only namespaced, reviewable project files:

- a managed Agent Smith block in `AGENTS.md`;
- `.agents/skills/agent-smith/` for Codex's progressive-disclosure workflow;
- four custom roles in `.codex/config.toml` with configs under `.codex/agents/`;
- a reviewable lifecycle hook under `.codex/hooks/` that loads project memory and enforces one final documentation-impact review;
- `.agent-smith/context.md`, a project-owned, versioned memory file that Codex reloads on session start, resume, clear, and compaction;
- `.agent-smith/config.json`, which records generated-file hashes for safe removal;
- a `.gitignore` entry for project-local runtime data.

Existing `AGENTS.md`, `.codex/config.toml`, and `.gitignore` content is preserved. Re-running `connect` updates the managed blocks and generated files idempotently.
If a generated role or skill file was edited locally, an update stops instead of overwriting it; inspect the change and pass `--force` only when replacement is intended.
The project-owned context file is never overwritten by reconnect, `--force`, or disconnect.

## Connect a project

### Git submodule (recommended)

From the project you want Codex to work on:

```bash
git submodule add https://github.com/artiehinz/agent-smith.git tools/agent-smith
git submodule update --init --recursive
python tools/agent-smith/smith.py connect .
python tools/agent-smith/smith.py doctor .
```

Restart Codex in the host project after connecting so it rebuilds its project instruction, skill, role, and hook catalog. Project-local command hooks require an explicit trust review: run `/hooks` in Codex once, inspect the Agent Smith entries, and trust them. Codex will request review again if their definitions change.

### Clone beside a project

```bash
git clone https://github.com/artiehinz/agent-smith.git
python agent-smith/smith.py connect path/to/your-project
```

### Install the CLI

```bash
python -m pip install "git+https://github.com/artiehinz/agent-smith.git"
agent-smith connect path/to/your-project
agent-smith doctor path/to/your-project
```

No LLM API key is required by Agent Smith itself.

## Connect once, keep context current

Once connected and trusted, ordinary Codex work in that repository does not require another Agent Smith command:

1. `SessionStart` injects the compact `.agent-smith/context.md` memory at startup, resume, clear, and after context compaction; `SubagentStart` gives the same memory to delegated agents.
2. `AGENTS.md` and the installed skill tell Codex to apply the workflow to every repository modification, while keeping small tasks direct.
3. `UserPromptSubmit` records the current worktree as an ignored per-turn baseline, so existing uncommitted work is not attributed to the new task.
4. When the turn changes material non-documentation files, `Stop` continues it once for a documentation delta review. Codex updates context and relevant docs only when durable knowledge changed; otherwise it explicitly confirms that no docs edit is needed.

This creates a reliable review gate without turning documentation into a timestamped activity log. Keep context factual, below 200 lines and 16 KiB. View it with:

```bash
python tools/agent-smith/smith.py context .
```

## Use it with Codex

Codex can select the installed skill automatically for repository modifications. Invoke it explicitly when you want to guarantee its full orchestration workflow for a task:

```text
Use $agent-smith to implement this change and verify it with the smallest effective agent topology.
```

The workflow chooses among:

- `direct`: one owner, no useful delegation;
- `structured`: primary writer plus bounded discovery or verification;
- `parallel`: independent work packages with isolated ownership and one integration owner.

Agent Smith installs `agent_smith_explorer`, `agent_smith_executor`, `agent_smith_tester`, and `agent_smith_reviewer` roles. The primary Codex thread remains responsible for architecture, integration, verification, commits, pushes, and the final verdict.

## Maintain or remove a connection

Update the submodule and regenerate managed files:

```bash
git submodule update --remote tools/agent-smith
python tools/agent-smith/smith.py connect .
python tools/agent-smith/smith.py doctor .
```

Disconnect safely:

```bash
python tools/agent-smith/smith.py disconnect .
```

`disconnect` removes generated files only when their hashes still match the manifest. Locally modified generated files are reported and preserved. `.agent-smith/context.md` is project-owned and remains available after disconnect; delete it manually only if you no longer want that project memory.

## Optional Headroom integration

[Headroom](https://github.com/headroomlabs-ai/headroom) is complementary rather than embedded. Agent Smith controls task routing and ownership; Headroom compresses model context and can share memory across agents. Keeping it optional avoids silently changing Codex's user-level proxy or MCP configuration.

```bash
uv tool install --python 3.13 "headroom-ai[all]"
headroom wrap codex
headroom doctor
```

Inspect availability and the undo command with:

```bash
python tools/agent-smith/smith.py headroom
```

See [docs/headroom.md](docs/headroom.md) for the integration boundary and operational cautions.

## Optional policy engine and dashboard

Classify a task directly:

```bash
python tools/agent-smith/smith.py route --breadth 6 --packages 3 --parallelism 2
```

Run the project-local dashboard:

```bash
python tools/agent-smith/smith.py dashboard .
```

Open `http://127.0.0.1:8000/dashboard/index.html`. Runtime state is written under the host project's ignored `.agent-smith/runtime/` directory, not inside the Agent Smith checkout.

Legacy Python consumers can still import `core.session` and call `start`, `resolve_launch_contract`, `enforce_launch_contract`, and `complete`. New integrations should prefer the native Codex skill and roles because Codex loads those surfaces automatically.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python smith.py connect path/to/a/temporary/project
python smith.py doctor path/to/a/temporary/project
```

The project supports Python 3.11 and newer and has no required third-party runtime dependencies.

## License

[MIT](LICENSE)
