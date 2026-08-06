"""Tests for policy API route helpers."""

from core.api_server.routes import policy_routes as routes
from core.policy import PreflightIntent, PreflightResult


def test_normalize_preflight_role_accepts_plan_synonyms() -> None:
    assert routes._normalize_preflight_role("executor") == "executor"
    assert routes._normalize_preflight_role("security-review") == "security review"
    assert routes._normalize_preflight_role("security_review") == "security review"
    assert routes._normalize_preflight_role("EXPLORER") == "explorer"


def test_normalize_preflight_role_rejects_unknown() -> None:
    assert routes._normalize_preflight_role("builder") is None
    assert routes._normalize_preflight_role(" ") is None


def test_normalize_pref_bool_supports_strings() -> None:
    assert routes._normalize_pref_bool(True) is True
    assert routes._normalize_pref_bool(False) is False
    assert routes._normalize_pref_bool("true") is True
    assert routes._normalize_pref_bool("off") is False
    assert routes._normalize_pref_bool(None, default=True) is True


def test_attestation_payload_records_expected_marker() -> None:
    intent = PreflightIntent(role="executor", model="gpt-5.6-luna", effort="medium")
    result = PreflightResult(
        intent=intent,
        marker="expected-marker",
        raw_output="marker: observed-marker\nrole: executor\nmodel: gpt-5.6-luna\neffort: medium",
        actual_role="executor",
        actual_model="gpt-5.6-luna",
        actual_effort="medium",
        actual_sandbox="read_only",
    )
    payload = routes._attestation_payload(result, marker_expected="expected-marker")
    assert payload["marker_expected"] == "expected-marker"
    assert payload["status"] == "mismatch"
