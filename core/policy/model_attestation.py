"""Runtime model/effort attestation data model."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    effort: str = "medium"

    def canonical(self) -> tuple[str, str]:
        return (self.name.strip().lower(), self.effort.strip().lower())


@dataclass(frozen=True)
class ModelAttestation:
    role: str
    intended: ModelSpec
    actual: ModelSpec | None = None
    note: str | None = None

    @property
    def status(self) -> str:
        if not self.intended:
            return "invalid"
        if self.actual is None:
            return "missing_actual"
        if self.intended.canonical() == self.actual.canonical():
            return "match"
        return "mismatch"


def is_fail_closed(attestation: ModelAttestation | None, *, cost_sensitive: bool = True) -> bool:
    """Return True when delegation should stop or require explicit guardrails."""
    if not cost_sensitive:
        return False
    if attestation is None:
        return True
    return attestation.status in {"mismatch", "missing_actual", "invalid"}

