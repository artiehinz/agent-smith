"""Context scout policy.

The scout is read-only and compact. It is used only when cheap discovery
signals are weak and a bounded context graph or static reconstruction would add
net confidence.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoutDecision:
    use_scout: bool
    reason: str


def should_run_context_scout(
    index_confidence: float = 1.0,
    runtime_discrepancy: bool = False,
    unfamiliar_packages: bool = False,
    requires_external_research: bool = False,
    graph_conflict_count: int = 0,
) -> ScoutDecision:
    """Return whether a read-only scout should be started."""
    if requires_external_research:
        return ScoutDecision(True, "requires external research")
    if runtime_discrepancy:
        return ScoutDecision(True, "runtime behavior differs from static assumptions")
    if unfamiliar_packages:
        return ScoutDecision(True, "several unfamiliar packages detected")
    if index_confidence < 0.55:
        return ScoutDecision(True, f"low index confidence ({index_confidence:.2f})")
    if graph_conflict_count > 1:
        return ScoutDecision(True, f"multiple graph/output conflicts: {graph_conflict_count}")
    return ScoutDecision(False, "direct execution path has sufficient context")
