"""Runtime preflight utilities for intent-vs-actual model verification."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from typing import Any


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
    status: str
    actual_role: str | None
    actual_model: str | None
    actual_effort: str | None
    actual_sandbox: str | None
    parse_error: str | None = None


def generate_preflight_marker() -> str:
    """Return a random marker token for traceability."""
    return f"policy-{uuid.uuid4()}"


def preflight_prompt(intent: PreflightIntent, marker: str) -> str:
    """Build a compact prompt expected to return model metadata."""
    return (
        "Preflight probe. Reply with machine-readable lines only.\n"
        f"marker: {marker}\n"
        f"role: {intent.role}\n"
        f"model: {intent.model}\n"
        f"effort: {intent.effort}\n"
        f"sandbox: {intent.sandbox}\n"
        "Use lines: marker, role, model, effort, sandbox."
    )


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_raw_output(raw_output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    text = (raw_output or "").strip()
    if not text:
        return parsed

    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return {str(k).strip().lower(): str(v or "").strip() for k, v in payload.items()}
    except json.JSONDecodeError:
        pass

    for line in text.splitlines():
        match = re.match(r"\s*([A-Za-z0-9_\- ]+)\s*:\s*(.+)\s*$", line)
        if not match:
            continue
        key = match.group(1).strip().lower().replace("-", "_")
        value = match.group(2).strip()
        if key:
            parsed[key] = value
    return parsed


def _coerce_parse_status(
    intent: PreflightIntent,
    marker: str,
    parsed: dict[str, str],
    raw_output: str,
) -> tuple[str, str | None, str | None, str | None, str | None]:
    observed_marker = parsed.get("marker", "")
    observed_role = parsed.get("role", "")
    observed_model = parsed.get("model", "")
    observed_effort = parsed.get("effort", "")
    observed_sandbox = parsed.get("sandbox", "")

    if not observed_marker and observed_model and observed_effort:
        observed_marker = marker

    if marker and observed_marker and observed_marker != marker:
        return (
            "mismatch",
            observed_role or None,
            observed_model or None,
            observed_effort or None,
            observed_sandbox or None,
        )

    if not observed_role and not observed_model and not observed_effort and not observed_sandbox:
        return (
            "missing_actual",
            None,
            None,
            None,
            observed_sandbox or None,
        )

    match_fields = (
        _normalise(observed_role) == _normalise(intent.role)
        and _normalise(observed_model) == _normalise(intent.model)
        and _normalise(observed_effort) == _normalise(intent.effort)
    )
    sandbox_match = _normalise(observed_sandbox) == _normalise(intent.sandbox)
    status = "match" if match_fields and sandbox_match else "mismatch"
    return (
        status,
        observed_role or None,
        observed_model or None,
        observed_effort or None,
        observed_sandbox or None,
    )


def parse_preflight_output(intent: PreflightIntent, raw_output: str, marker: str) -> PreflightResult:
    """Parse worker output and return an attestation outcome."""
    parsed = _parse_raw_output(raw_output)
    status, role, model, effort, sandbox = _coerce_parse_status(intent, marker, parsed, raw_output)
    parse_error = None
    if not raw_output.strip():
        status = "missing_actual"
        parse_error = "empty preflight output"
    elif not parsed:
        parse_error = "unable to parse preflight output"
    if status == "mismatch" and parsed.get("marker") and _normalise(parsed.get("marker")) == _normalise(marker):
        # Ensure mismatch is tied to actual values when marker is valid.
        parse_error = None

    return PreflightResult(
        intent=intent,
        marker=marker,
        raw_output=(raw_output or "").strip(),
        status=status,
        actual_role=role,
        actual_model=model,
        actual_effort=effort,
        actual_sandbox=sandbox,
        parse_error=parse_error,
    )


def attestation_payload(result: PreflightResult, marker_expected: str | None) -> dict[str, Any]:
    """Return a JSON-serializable preflight payload."""
    return {
        "status": result.status,
        "marker_expected": marker_expected,
        "marker": result.marker,
        "intent": {
            "role": result.intent.role,
            "model": result.intent.model,
            "effort": result.intent.effort,
            "sandbox": result.intent.sandbox,
        },
        "actual": {
            "role": result.actual_role,
            "model": result.actual_model,
            "effort": result.actual_effort,
            "sandbox": result.actual_sandbox,
        },
        "parse_error": result.parse_error,
        "raw_output": result.raw_output,
    }


def run_preflight_probe(
    intent: PreflightIntent,
    marker: str,
    *,
    timeout_seconds: int = 20,
    command: list[str] | None = None,
) -> PreflightResult:
    """Execute a local probe and parse the resulting metadata."""
    probe = preflight_prompt(intent, marker)
    if command is None:
        command = [
            "codex",
            "exec",
            "--model",
            intent.model,
            "--config",
            f'model_reasoning_effort="{intent.effort}"',
            "--config",
            "agents.max_depth=0",
        ]

    if shutil.which("codex") is None:
        return PreflightResult(
            intent=intent,
            marker=marker,
            raw_output="codex executable unavailable",
            status="missing_actual",
            actual_role=None,
            actual_model=None,
            actual_effort=None,
            actual_sandbox=intent.sandbox,
            parse_error="codex executable unavailable",
        )

    try:
        process = subprocess.run(
            command,
            input=probe,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = (process.stdout or "").strip()
        if not output:
            output = (process.stderr or "").strip() or probe
        return parse_preflight_output(intent, output, marker)
    except subprocess.TimeoutExpired as exc:
        return PreflightResult(
            intent=intent,
            marker=marker,
            raw_output=probe,
            status="missing_actual",
            actual_role=None,
            actual_model=None,
            actual_effort=None,
            actual_sandbox=intent.sandbox,
            parse_error=f"preflight timed out after {timeout_seconds}s: {exc}",
        )
    except FileNotFoundError:
        return PreflightResult(
            intent=intent,
            marker=marker,
            raw_output="codex unavailable",
            status="missing_actual",
            actual_role=None,
            actual_model=None,
            actual_effort=None,
            actual_sandbox=intent.sandbox,
            parse_error="codex unavailable",
        )
    except Exception as exc:
        return PreflightResult(
            intent=intent,
            marker=marker,
            raw_output=probe,
            status="mismatch",
            actual_role=None,
            actual_model=None,
            actual_effort=None,
            actual_sandbox=intent.sandbox,
            parse_error=f"preflight probe failed: {exc}",
        )
