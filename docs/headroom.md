# Headroom integration

Agent Smith and Headroom solve different parts of the agent workflow:

| Layer | Agent Smith | Headroom |
|---|---|---|
| Task routing and agent ownership | Yes | No |
| Codex role definitions and verification policy | Yes | No |
| Context compression and reversible retrieval | No | Yes |
| Cross-agent memory | No | Optional |
| Required for the other tool | No | No |

## Recommended boundary

Keep Headroom as an operator-installed, user-level companion. Launch Codex through Headroom when working on context-heavy repositories, then let the repo-local Agent Smith skill control decomposition and verification inside that session.

```bash
uv tool install --python 3.13 "headroom-ai[all]"
headroom wrap codex
headroom doctor
```

Undo the durable wrapper configuration with:

```bash
headroom unwrap codex
```

Agent Smith deliberately does not install Headroom, start its proxy, or edit global Codex MCP settings. Those actions affect projects beyond the current repository and should remain an explicit operator choice.

## Operational cautions

- Treat the proxy and cross-agent memory store as part of the local data boundary.
- Run `headroom doctor` after upgrades and before relying on compression metrics.
- Use absolute executable paths in MCP configuration when Codex cannot inherit the tool's `PATH`.
- Benchmark representative work before enabling output shaping or other behavior-changing options for a team.

Sources: [Headroom repository](https://github.com/headroomlabs-ai/headroom) and [Headroom documentation](https://headroom-docs.vercel.app/).
