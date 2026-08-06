# Agent Smith Policy Bootstrap

This repo contains the policy execution bootstrap for Agent Smith: policy decisions,
launch enforcement, preflight automation, and policy telemetry.

## Connect this repo to a new project

1. Add as a submodule (recommended):

```bash
git submodule add https://github.com/artiehinz/agent-smith.git agent-smith
git submodule update --init --recursive
```

2. Install Python dependencies for your host project, then import:

```python
from core import session as scan_session
from core.policy import ...
```

3. Start a policy-controlled session:

```python
scan_session.start("https://target", depth="standard", scan_mode="benchmark")
```

4. Before launching any worker, ask the local policy contract:

```python
decision = scan_session.resolve_launch_contract("executor", intended_model="gpt-5.6-luna", intended_effort="medium")
if not decision["ok"]:
    # block or raise approval, do not start worker
    ...
if decision["launch_authorized"] and decision["action"] == "authorized":
    # run selected command/path from decision["command"]
elif decision["action"] == "needs_approval":
    # present approval surface
elif decision["action"] == "blocked":
    # stop delegation
```

4a. For orchestrators that want a stable single-step gate:

```python
plan = scan_session.enforce_launch_contract(
    "executor",
    intended_model="gpt-5.6-luna",
    intended_effort="medium",
)
if plan["ok"] and plan["launch"]:
    # launch using decision in plan["contract"]
elif plan["action"] == "needs_approval":
    # show explicit approval UI
else:
    # block delegation
```

5. Optional API-driven orchestration:

- `POST /api/policy/launch-plan` returns the same decision contract.
- `GET /api/policy` returns live policy blob.
- `GET /api/policy/preflight` returns current preflight + backend decision telemetry.
- `GET /api/policy/tasks` returns task ledger with route/status filters.

6. Launch the dashboard:

```bash
python -m core.api_server
# visit http://localhost:8000
```

## Bootstrap helpers

- Run `tools/bootstrap/policy_repos.ps1` to refresh reference repos under:
  - `references/codex_workflow`
  - `references/codex_workflows`
  - `references/codex-agent-config`
- These folders are intentionally in `.gitignore` and kept local.

## Required contract fields for enforcement consumers

`core.session.resolve_launch_contract`, `core.session.enforce_launch_contract`, and `POST /api/policy/launch-plan` return:

- `enabled`, `role`, `route`, `selected_backend`, `fallback_backend`
- `requires_approval`, `fail_closed`, `block_delegation`, `command`, `reason`
- `launch_authorized`, `status` (`authorized`, `needs_approval`, `blocked`), `route_hint`
- `command_path`, `requires_runtime_proxy` (helper routing metadata)
