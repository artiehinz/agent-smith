# Policy: Token limits

## Purpose

Control token consumption by route and role so long tasks do not drift into cost-heavy failures.

## Defaults

- direct: 8,000 hard / 6,400 soft
- structured: 30,000 hard / 22,000 soft
- parallel: 60,000 hard / 42,000 soft

## Worker ceilings

- structured route: 14,000 hard / 11,000 soft
- parallel route: 22,000 hard / 17,000 soft
- direct route: no worker cap (no delegated worker by default)

## Enforcement states

- `ok`: under soft limits
- `soft_limit`: near budget limit, should suggest compression
- `hard_limit`: stop further expansion and escalate
