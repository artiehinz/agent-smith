## Route Classifier Policy

Automatic route classifier
=========================

Implementation status: implemented

What this means
- Route is selected by the policy classifier using the weighted signals defined by the plan:
  - task breadth
  - number of affected packages
  - uncertainty
  - verification complexity
  - independent work opportunities
  - estimated agent overhead
- Supported routes remain:
  - `direct`
  - `structured`
  - `parallel`
- User overrides are persisted as `route_hint` and may force selection.

Current wiring
- `core/policy/route_classifier.py` contains the policy math and return shape.
- `core/session/lifecycle.py` builds and stores route policy with `_default_route_policy` and injects it into scan sessions.
- `core/policy/task_ledger.py` records route classification input/output for traceability.
- `core/api_server/routes/policy_routes.py` exposes route read/set endpoints.

Next action
- Add telemetry feedback from real tasks once route-quality reporting is available.
