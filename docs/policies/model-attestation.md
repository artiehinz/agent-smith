## Runtime model attestation

Do not assume configured values are the values actually used at runtime.

- Store both intended and actual fields:
  - `role`
  - `intended.model`
  - `intended.effort`
  - `actual.model`
  - `actual.effort`
  - `status` (`match`, `mismatch`, `missing_actual`)

## Fail-closed behavior

- For cost-sensitive roles, `mismatch` or `missing_actual` is treated as a hard gate by
  default.
- Fallback options:
  - use explicit CLI worker invocation
  - ask for approval
  - use parent model inside declared budget
