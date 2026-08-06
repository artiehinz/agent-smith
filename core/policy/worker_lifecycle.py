"""Evidence policy for worker responses and lifecycle transitions."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import json
import re


class WorkerLifecycleAction(str, Enum):
    CONTINUE = "continue"
    RETRY = "retry"
    REPLACE = "replace"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class WorkerLifecycleState:
    evidence_free_turns: int = 0
    replacements: int = 0
    max_evidence_free_turns: int = 1
    max_replacements: int = 1


def _has_evidence_marker(value: object) -> bool:
    if isinstance(value, dict):
        keys = {
            "changed_files",
            "commands",
            "result",
            "test_failure",
            "evidence",
            "path",
            "artifact",
            "status",
        }
        if keys.intersection(set(value.keys())):
            return True
        return False
    if isinstance(value, str):
        text = value.lower()
        if re.search(r"\.[a-z0-9_]+\b", text):
            return True
        if any(token in text for token in ("ran", "result", "passed", "failed", "blocked", "evidence", "changed")):
            return True
    return False


def update_worker_lifecycle(
    state: WorkerLifecycleState | None,
    message: object,
) -> tuple[WorkerLifecycleState, WorkerLifecycleAction]:
    """Evaluate a worker turn and return updated state plus action."""
    current = state or WorkerLifecycleState()
    if _has_evidence_marker(message):
        return current, WorkerLifecycleAction.CONTINUE

    if current.evidence_free_turns < current.max_evidence_free_turns:
        return replace(current, evidence_free_turns=current.evidence_free_turns + 1), WorkerLifecycleAction.RETRY

    if current.replacements < current.max_replacements:
        return (
            replace(
                current,
                replacements=current.replacements + 1,
                evidence_free_turns=0,
            ),
            WorkerLifecycleAction.REPLACE,
        )

    return current, WorkerLifecycleAction.ESCALATE
