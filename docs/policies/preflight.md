# Policy: Agent preflight

## Purpose

Validate runtime worker launch settings before delegation.

- intended role
- intended model
- intended reasoning effort
- intended sandbox mode

## Contract

A worker preflight prompt must include a fixed marker token and explicit metadata.
The parser checks:

- marker present
- role, model, effort, and sandbox fields present
- exact match against intent for strong- and medium-sensitive roles

## Outcomes

- `match`: all observed values match intent
- `mismatch`: one or more values differ
- `missing_actual`: some expected fields missing
- `marker_missing`: marker not seen in output
- `parse_error`: response could not be parsed

## Integration behavior

- Match -> native worker path remains preferred
- Mismatch or missing on sensitive roles -> explicit `codex exec` fallback
- Mismatch on low-sensitivity tasks may continue with native worker and visible warning
