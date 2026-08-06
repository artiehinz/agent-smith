"""Tests for backend selection policy."""

from core.policy.agent_backends import AgentBackend, choose_backend
from core.policy.model_attestation import ModelAttestation, ModelSpec


def test_match_uses_native_backend():
    att = ModelAttestation(
        role="executor",
        intended=ModelSpec(name="gpt-5.6-luna", effort="medium"),
        actual=ModelSpec(name="gpt-5.6-luna", effort="medium"),
    )
    result = choose_backend("executor", "gpt-5.6-luna", "medium", attestation=att)
    assert result.selected_backend == AgentBackend.NATIVE
    assert result.fail_closed is False


def test_cost_sensitive_mismatch_uses_explicit():
    att = ModelAttestation(
        role="executor",
        intended=ModelSpec(name="gpt-5.6-luna", effort="medium"),
        actual=ModelSpec(name="gpt-5.6-sol", effort="ultra"),
    )
    result = choose_backend("executor", "gpt-5.6-luna", "medium", attestation=att)
    assert result.selected_backend == AgentBackend.EXPLICIT
    assert result.fail_closed is True
