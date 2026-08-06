"""Tests for runtime model attestation helpers."""

from core.policy.model_attestation import ModelAttestation, ModelSpec, attestation_report, is_fail_closed


def test_attestation_match():
    att = ModelAttestation(
        role="executor",
        intended=ModelSpec(name="gpt-5.6-luna", effort="medium"),
        actual=ModelSpec(name="gpt-5.6-luna", effort="medium"),
    )
    assert att.status == "match"
    report = attestation_report(att)
    assert report["status"] == "match"


def test_attestation_mismatch():
    att = ModelAttestation(
        role="executor",
        intended=ModelSpec(name="gpt-5.6-luna", effort="medium"),
        actual=ModelSpec(name="gpt-5.6-sol", effort="ultra"),
    )
    assert att.status == "mismatch"
    assert is_fail_closed(att, cost_sensitive=True) is True
