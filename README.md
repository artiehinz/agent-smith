# Agent Smith Policy Bootstrap

This repo contains the policy orchestration, launch, preflight, and dashboard wiring for Agent Smith.

## How to connect to a new project repo

1. Add this repo to your project as a git submodule:

```bash
git submodule add https://github.com/artiehinz/agent-smith.git agent-smith
git submodule update --init --recursive
```

2. Point your project entrypoint at this repo’s policy/session APIs.

- Start by importing policy modules from `core.policy` and session entrypoints from `core.session`.
- Use `/api/policy/launch-plan` to get launch decisions before starting any worker/orchestrator run.
- Re-use the provided session ledger + policy writes for telemetry and recovery.

3. Configure environment and session intent.

- Use the existing `.env` variables from this repo’s expected policy defaults.
- Keep preflight/launch mode defaults as needed for your project (`auto` for normal, `manual` where you want pasted evidence).

4. Run the API server and dashboard.

```bash
# start the API server
python -m core.api_server

# open dashboard
open http://localhost:8000
```

5. Point your external runner/orchestrator to the launch contract fields returned by `policy_launch_plan`:

- `enabled`
- `route`
- `selected_backend`
- `fallback_backend`
- `requires_approval`
- `fail_closed`
- `block_delegation`
- `command` (explicit path when used)
- `reason`

## Notes

- This repo is designed to stay as the local policy source of truth.
- Bootstrap helper folders (`references/`, `skills/`, `.codex-control/`, etc.) are in `.gitignore` so they stay local and out of Git history.
