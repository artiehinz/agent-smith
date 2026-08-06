# Agent Smith Policy Bootstrap

This repository provides a policy-first execution layer for Agent Smith:
policy routing, preflight governance, launch enforcement, and policy telemetry.

You can wire it into another project without moving it into Python package tooling.

## Quick connect from a new repo

### Option 1: submodule (recommended)

```bash
git submodule add https://github.com/artiehinz/agent-smith.git agent-smith
git submodule update --init --recursive
```

Then initialize a Python environment:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
```

Add the submodule path to `PYTHONPATH` when importing:

```powershell
$env:PYTHONPATH = "$(Resolve-Path .\agent-smith);$env:PYTHONPATH"
```

```bash
export PYTHONPATH="$(pwd)/agent-smith:$PYTHONPATH"
```

### Option 2: plain copy

Copy the entire folder into your repo as `agent-smith` and add it to `PYTHONPATH` with the
same commands above.

## Minimal API/SDK usage

From your orchestration code:

```python
import sys
from pathlib import Path

# Example if repo is under ./agent-smith
sys.path.insert(0, str(Path(__file__).resolve().parent / "agent-smith"))

from core import session as scan_session
```

Start a policy-aware scan:

```python
session = scan_session.start("https://target.example", depth="standard", scan_mode="benchmark")
```

Before starting any worker, resolve policy first:

```python
decision = scan_session.resolve_launch_contract(
    role="executor",
    intended_model="gpt-5.6-luna",
    intended_effort="medium",
)
```

```python
if decision.get("ok") and decision.get("launch_authorized"):
    # launch from decision["command"] / decision["command_path"]
    ...
elif decision.get("action") == "needs_approval":
    # show operator approval UI
    ...
else:
    # stop delegation
    ...
```

If you prefer one stable call for orchestration:

```python
plan = scan_session.enforce_launch_contract(
    role="executor",
    intended_model="gpt-5.6-luna",
    intended_effort="medium",
)
```

## Dashboard and API

Use the built-in HTTP bridge for local control and policy views:

```bash
python -m core.api_server
# or:
python tools/run_policy_dashboard.py
```

Then open:

`http://127.0.0.1:8000/dashboard/index.html`

Useful endpoints:

- `GET /api/policy`
- `GET /api/policy/preflight`
- `GET /api/policy/tasks`
- `POST /api/policy/route`
- `POST /api/policy/preflight`
- `POST /api/policy/repair`
- `POST /api/policy/launch-plan` (if your orchestrator uses policy contracts via HTTP)

## Bootstrap helper repos

Run this once per environment to populate local-only references:

```bash
powershell -ExecutionPolicy Bypass -File tools/bootstrap/policy_repos.ps1
```

Artifacts are written to:
- `references/codex_workflow`
- `references/codex_workflows`
- `references/codex-agent-config`

These directories are intentionally `.gitignore`d and should remain out of commits.

## Launch contract fields expected by consumers

The decision contract includes:
- `enabled`
- `role`
- `route`
- `route_hint`
- `selected_backend`
- `fallback_backend`
- `requires_approval`
- `fail_closed`
- `block_delegation`
- `command`
- `command_path`
- `requires_runtime_proxy`
- `launch_authorized`
- `status` (`authorized`, `needs_approval`, `blocked`)

## Common setup checklist (new project)

1. Add or copy this repo into your project.
2. Add `agent-smith` to `PYTHONPATH`.
3. Import `core.session` and call launch contract before any worker starts.
4. Start dashboard/API if you want operator controls.
5. Confirm `/api/policy` and `/api/policy/preflight` return data before declaring deployment.
