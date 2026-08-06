"""Agent backend selection policy for worker launch and fallback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model_attestation import ModelAttestation, is_fail_closed


class AgentBackend(str, Enum):
    NATIVE = "native_subagent"
    EXPLICIT = "explicit_codex_exec"


@dataclass(frozen=True)
class BackendDecision:
    role: str
    selected_backend: AgentBackend
    fallback_backend: AgentBackend | None
    fail_closed: bool
    requires_approval: bool
    reason: str


def _coerce_explicit_unavailable(
    role: str,
    decision: BackendDecision,
    *,
    explicit_worker_available: bool,
) -> BackendDecision:
    """If explicit execution is required but unavailable, fail-closed on native with approval."""
    if decision.selected_backend != AgentBackend.EXPLICIT:
        return decision
    if explicit_worker_available:
        return decision
    return BackendDecision(
        role=role,
        selected_backend=AgentBackend.NATIVE,
        fallback_backend=None,
        fail_closed=True,
        requires_approval=True,
        reason=(
            f"{decision.reason} Explicit worker unavailable for role={role}; "
            "falling back to native under fail-closed."
        ),
    )


def prefer_explicit_workers(role: str) -> bool:
    """Roles that usually warrant stricter model guarantees."""

    return role.lower() in {"executor", "tester", "reviewer", "security review", "security_review"}


def choose_backend(
    role: str,
    intended_model: str,
    intended_effort: str,
    *,
    attestation: ModelAttestation | None = None,
    explicit_worker_available: bool = True,
) -> BackendDecision:
    """Pick backend + fallback strategy based on attestation confidence."""

    if attestation is None:
        if prefer_explicit_workers(role):
            return _coerce_explicit_unavailable(
                role,
                BackendDecision(
                    role=role,
                    selected_backend=AgentBackend.EXPLICIT,
                    fallback_backend=AgentBackend.NATIVE if explicit_worker_available else None,
                    fail_closed=True,
                    requires_approval=False,
                    reason=(
                        f"No runtime attestation for role={role}; use explicit worker "
                        f"for deterministic model={intended_model} effort={intended_effort}."
                    ),
                ),
                explicit_worker_available=explicit_worker_available,
            )
        return BackendDecision(
            role=role,
            selected_backend=AgentBackend.NATIVE,
            fallback_backend=AgentBackend.EXPLICIT if explicit_worker_available else None,
            fail_closed=False,
            requires_approval=False,
            reason=f"No preflight result for role={role}; use native by default.",
        )

    if attestation.status == "match":
        return BackendDecision(
            role=role,
            selected_backend=AgentBackend.NATIVE,
            fallback_backend=AgentBackend.EXPLICIT if explicit_worker_available else None,
            fail_closed=False,
            requires_approval=False,
            reason="Attestation matches configured model and effort.",
        )

    if attestation.status in {"mismatch", "missing_actual"} and prefer_explicit_workers(role):
        return _coerce_explicit_unavailable(
            role,
            BackendDecision(
                role=role,
                selected_backend=AgentBackend.EXPLICIT,
                fallback_backend=AgentBackend.NATIVE if explicit_worker_available else None,
                fail_closed=attestation.status in {"mismatch", "missing_actual"},
                requires_approval=False,
                reason=(
                    f"Cost-sensitive role and preflight status={attestation.status}; "
                    "use explicit worker for model/effort control."
                ),
            ),
            explicit_worker_available=explicit_worker_available,
        )

    return _coerce_explicit_unavailable(
        role,
        BackendDecision(
            role=role,
            selected_backend=AgentBackend.NATIVE,
            fallback_backend=AgentBackend.EXPLICIT if explicit_worker_available else None,
            fail_closed=is_fail_closed(attestation, cost_sensitive=prefer_explicit_workers(role)),
            requires_approval=False,
            reason=(
                f"Using native backend for role={role} with fallback allowed "
                f"(preflight status={attestation.status})."
            ),
        ),
        explicit_worker_available=explicit_worker_available,
    )


def explicit_worker_args(*, model: str, effort: str, max_depth: int = 0) -> list[str]:
    """Build CLI arguments for deterministic explicit worker launch."""

    return [
        "codex",
        "exec",
        "--model",
        model,
        "--config",
        f'model_reasoning_effort="{effort}"',
        "--config",
        f"agents.max_depth={max_depth}",
    ]


def should_disable_delegation(selected_backend: AgentBackend, *, attestation: ModelAttestation | None) -> bool:
    """Whether to block delegation based on fail-closed policy."""

    if selected_backend == AgentBackend.EXPLICIT:
        return False
    return attestation is not None and is_fail_closed(attestation, cost_sensitive=True)
