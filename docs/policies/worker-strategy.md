## Worker packet strategy

Use bounded packets only, keep follow-up messages delta-only.

- Initial packet includes:
  - `task_id`
  - `role`
  - `outcome` target
  - `scope.read`, `scope.write`, `scope.protected`
  - `acceptance`
  - `context_refs`
  - `return` fields
- Never resend full project docs or old task payloads.
- Follow-up packets should include only changed keys (`as_delta_message`).

## Worker limits

- Initial packet budget: 300-500 tokens
- Progress event: 100-160 tokens
- Follow-up delta: 150-220 tokens
- Final report: 250-420 tokens
