# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities through a private GitHub security advisory for this repository. Do not include credentials, private source code, or exploit data in a public issue.

## Security boundary

Agent Smith writes project-local Codex configuration and runtime state. The dashboard binds to loopback by default and serves only its allowlisted dashboard assets. Do not expose it on a public interface without adding authentication and transport security.

Optional third-party tools such as Headroom are outside Agent Smith's trust and update boundary. Review their configuration and data handling separately.
