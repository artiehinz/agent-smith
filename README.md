# Agent Smith

Agent Smith is a repo-local orchestration layer for Codex. It connects durable project guidance, a reusable workflow skill, namespaced subagent roles, an optional policy engine, and a local dashboard without replacing a project's existing instructions.

The repository is currently **alpha**. The Codex connector and doctor workflow are the supported integration path; the older scan/session API remains available for compatibility.

## What a connection installs

Running `connect` adds only namespaced, reviewable project files:

- a managed Agent Smith block in `AGENTS.md`;
- `.agents/skills/agent-smith/` for Codex's progressive-disclosure workflow;
- four custom roles in `.codex/config.toml` with configs under `.codex/agents/`;
- `.agent-smith/config.json`, which records generated-file hashes for safe removal;
- a `.gitignore` entry for project-local runtime data.

Existing `AGENTS.md`, `.codex/config.toml`, and `.gitignore` content is preserved. Re-running `connect` updates the managed blocks and generated files idempotently.
If a generated role or skill file was edited locally, an update stops instead of overwriting it; inspect the change and pass `--force` only when replacement is intended.

## Connect a project

### Git submodule (recommended)

From the project you want Codex to work on:

```bash
git submodule add https://github.com/artiehinz/agent-smith.git tools/agent-smith
git submodule update --init --recursive
python tools/agent-smith/smith.py connect .
python tools/agent-smith/smith.py doctor .
```

Restart Codex in the host project after connecting so it rebuilds its project instruction, skill, and role catalog.

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

## Use it with Codex

Codex can select the installed skill automatically for non-trivial repository work. Invoke it explicitly when desired:

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

`disconnect` removes generated files only when their hashes still match the manifest. Locally modified generated files are reported and preserved.

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
