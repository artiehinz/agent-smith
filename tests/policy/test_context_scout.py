"""Tests for context scout policy selection."""

from core.policy.context_scout import should_run_context_scout


def test_context_scout_not_needed_when_confident():
    decision = should_run_context_scout(
        index_confidence=0.9,
        runtime_discrepancy=False,
        unfamiliar_packages=False,
        requires_external_research=False,
        graph_conflict_count=0,
    )
    assert decision.use_scout is False
    assert decision.reason.startswith("direct execution path")


def test_context_scout_triggers_on_low_confidence():
    decision = should_run_context_scout(index_confidence=0.2)
    assert decision.use_scout is True
    assert "low index confidence" in decision.reason
