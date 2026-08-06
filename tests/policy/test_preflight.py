"""Tests for preflight marker contracts."""

from core.policy.preflight import (
    PreflightIntent,
    generate_preflight_marker,
    preflight_prompt,
    parse_preflight_output,
)


def test_parse_preflight_match():
    intent = PreflightIntent(role="explorer", model="gpt-5.6-luna", effort="medium")
    marker = generate_preflight_marker()
    output = "\n".join(
        [
            preflight_prompt(intent, marker),
            marker,
            "role: explorer",
            "model: gpt-5.6-luna",
            "effort: medium",
            "sandbox: read_only",
        ]
    )

    result = parse_preflight_output(intent, output, marker)
    assert result.status == "match"
    assert result.actual_model == "gpt-5.6-luna"


def test_marker_missing_marks_failure():
    intent = PreflightIntent(role="explorer", model="gpt-5.6-luna", effort="medium")
    marker = generate_preflight_marker()
    output = "role: explorer\nmodel: gpt-5.6-luna\neffort: medium\nsandbox: read_only"

    result = parse_preflight_output(intent, output, marker)
    assert result.status == "marker_missing"
