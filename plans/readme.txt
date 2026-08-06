Policy execution plan bootstrap
==============================

Purpose
-------
- Track the execution plan and policy work in this repository.
- Keep missing artifacts discoverable so implementation work can start without re-discovery.

What was prepared
-----------------
- External workflow reference repos checked out under `references/`:
  - `references/codex-workflow`
  - `references/codex-agent-config`
  - `references/codex_workflows`
- Policy API route scaffold added:
  - `core/api_server/routes/policy_routes.py`
- Policy UI scaffold folders added:
  - `dashboard/policy/policy.html`
  - `dashboard/policy/policy.js`
  - `dashboard/tabs/policy.html`
  - `dashboard/js/policy.js`
- Local bootstrap helper:
  - `tools/bootstrap/policy_repos.ps1`
- Plan notes:
  - `plans/readme.txt` (this file)
  - `plans/implementation/*.md`
  - `docs/policies/design-notes/*.md`

Next work (in order)
--------------------
1. Finish wiring policy artifacts into active worker orchestration paths (not yet connected end-to-end).
2. Drive policy-led dashboard controls from real launch/repair actions (route reset + repair counters).
3. Replace manual preflight copy/paste with automatic codex-version probe in production workflow.
