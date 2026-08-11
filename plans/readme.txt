Agent Smith planning archive
============================

The files under plans/ are historical design and implementation artifacts from
the original policy-engine prototype. They are retained for decision context,
not as current setup instructions or a source of runtime truth.

Current supported integration
-----------------------------
- README.md documents project connection and operation.
- agent_smith/integration.py owns connect, doctor, and disconnect behavior.
- agent_smith/templates/agent-smith/ owns the repo-local Codex skill.
- core/policy/ contains the optional route and launch-policy engine.
- tests/ contains the executable behavior contract.

When a plan conflicts with source, tests, or README.md, treat the plan as
superseded. New implementation work should update executable tests and current
documentation rather than marking these archived plans as live state.
