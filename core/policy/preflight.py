"""Runtime preflight helpers for model attestation before worker delegation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Any
from uuid import uuid4

_MARKER_PREFIX = "PRECHECK_OK"
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def generate_preflight_marker() -> str:
    """Return a compact marker token for preflight validation."""

    return f"{_MARKER_PREFIX}:{uuid4().hex[:10]}"


@dataclass(frozen=True)
class PreflightIntent:
    role: str
    model: str
    effort: str
    sandbox: str = "read_only"


@dataclass(frozen=True)
class PreflightResult:
    intent: PreflightIntent
    marker: str
    raw_output: str
    actual_model: str | None = None
    actual_effort: str | None = None
    actual_sandbox: str | None = None
    actual_role: str | None = None
    parse_error: str | None = None

    @property
    def status(self) -> str:
        if self.parse_error:
            return "parse_error"
        if self.actual_model is None or self.actual_effort is None:
            return "missing_actual"
        if self.marker not in self.raw_output:
            return "marker_missing"
        if self.actual_model != self.intent.model or self.actual_effort != self.intent.effort:
            return "mismatch"
        if self.actual_role is not None and self.actual_role != self.intent.role:
            return "role_mismatch"
        if self.actual_sandbox is not None and self.actual_sandbox != self.intent.sandbox:
            return "sandbox_mismatch"
        return "match"


def preflight_prompt(intent: PreflightIntent, marker: str) -> str:
    """Build the probe instruction for a deterministic worker response."""

    return (
        "Reply only with one JSON object and the marker token.\n"
        f"Expected marker: {marker}.\n"
        "Output only JSON with this shape and nothing else:\n"
        f'{{"role":"{intent.role}","model":"{intent.model}",'
        f'"effort":"{intent.effort}","sandbox":"{intent.sandbox}",'
        f'"marker":"{marker}"}}\n'
    )


def _extract_key_values(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip().rstrip(",")
        if key in {"role", "model", "effort", "sandbox", "marker"}:
            parsed[key] = value.strip('"')

    if not parsed:
        json_match = _JSON_RE.search(text)
        if json_match:
            try:
                payload = json.loads(json_match.group(0))
            except Exception:
                return parsed
            for key in ("role", "model", "effort", "sandbox", "marker"):
                value = payload.get(key)
                if isinstance(value, str):
                    parsed[key] = value
    return parsed


def parse_preflight_output(intent: PreflightIntent, output: str, marker: str) -> PreflightResult:
    """Parse one probe output into an attestation result."""

    normalized = (output or "").strip()
    if not normalized:
        return PreflightResult(
            intent=intent,
            marker=marker,
            raw_output="",
            parse_error="empty output",
        )

    parsed = _extract_key_values(normalized)
    if not parsed:
        return PreflightResult(
            intent=intent,
            marker=marker,
            raw_output=normalized,
            parse_error="unparseable output",
        )

    return PreflightResult(
        intent=intent,
        marker=parsed.get("marker", marker),
        raw_output=normalized,
        actual_role=parsed.get("role"),
        actual_model=parsed.get("model"),
        actual_effort=parsed.get("effort"),
        actual_sandbox=parsed.get("sandbox"),
    )


def preflight_report(results: list[PreflightResult]) -> dict[str, Any]:
    """Create a compact role-indexed summary for dashboards and logs."""

    rows: dict[str, Any] = {}
    for result in results:
        rows[result.intent.role] = {
            "status": result.status,
            "intended": asdict(result.intent),
            "actual": {
                "role": result.actual_role,
                "model": result.actual_model,
                "effort": result.actual_effort,
                "sandbox": result.actual_sandbox,
            },
            "parse_error": result.parse_error,
        }
    return rows
