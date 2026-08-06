Automatic route classifier
=========================

Implementation status: ✅ implemented

What this means
- Use `core/policy/route_classifier.py` as the policy source of truth.
- Route is chosen from route-context signals:
  - task breadth
  - affected packages
  - uncertainty
  - verification complexity
  - independent work opportunities
  - estimated agent overhead
- Route hints (`direct|structured|parallel`) are supported and marked `override_applied`.

Current wiring
- Session-start route policy is built in `mcp_server/session_tools/start.py` via `_build_route_policy`.
- Runtime policy is attached to `session["policy"]`.
- Route reset on completion is handled in `core/session/lifecycle.py`.
- Route controls are exposed at `POST /api/policy/route`.

Next action
- Tune score weights/thresholds only when we have production telemetry; keep defaults stable for now.
