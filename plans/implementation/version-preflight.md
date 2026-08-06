Version / codex-build preflight
=============================

Implementation status: ✅ implemented (manual path)

What this means
- Per-version probe evidence is captured and evaluated before trust in delegation.
- Supports fallback policy when verification confidence is low.

Current wiring
- Policy preflight endpoint captures role/model/effort evidence:
  - `POST /api/policy/preflight`
- Dashboard input can run manual probe parsing via preflight form.
- Backend selection logic consumes attestation status and may require explicit worker use.

Next action
- Add automatic launcher for version/build probe and scheduled refresh on client/build update events.
