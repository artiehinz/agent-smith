"""Runtime attestation for intended vs actual worker model configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    effort: str = "medium"


@dataclass(frozen=True)
class ModelAttestation:
    role: str
    intended: ModelSpec
    actual: ModelSpec | None = None

    @property
    def status(self) -> str:
        if not self.actual:
            return "missing_actual"
        if (
            self.intended.name == self.actual.name
            and self.intended.effort == self.actual.effort
        ):
            return "match"
        return "mismatch"


def attestation_report(att: ModelAttestation) -> dict[str, str]:
    actual_model = att.actual.name if att.actual else "unknown"
    actual_effort = att.actual.effort if att.actual else "unknown"
    return {
        "role": att.role,
        "intended_model": att.intended.name,
        "intended_effort": att.intended.effort,
        "actual_model": actual_model,
        "actual_effort": actual_effort,
        "status": att.status,
    }


def is_fail_closed(att: ModelAttestation, cost_sensitive: bool = False) -> bool:
    if not cost_sensitive:
        return att.status == "missing_actual"
    return att.status in {"missing_actual", "mismatch"}
