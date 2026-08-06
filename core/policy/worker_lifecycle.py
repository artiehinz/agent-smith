"""Evidence policy for delegated workers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class LifecycleAction(str, Enum):
    CONTINUE = "continue"
    RETRY = "retry"
    REPLACE = "replace"
    ESCALATE = "escalate"


@dataclass
class EvidenceEvent:
    worker_id: str
    message: str
    turn: int
    has_evidence: bool


@dataclass
class WorkerLifecycle:
    worker_id: str
    evidence_free_turns: int = 0
    replaced: bool = False
    turns: int = 0
    evidence_log: list[EvidenceEvent] = field(default_factory=list)


_SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PATH_RE = re.compile(r"([A-Za-z0-9_./-]+\\.[A-Za-z0-9]{1,10})")
_CMD_RE = re.compile(r"\\b(ran|run|executed|command|cmd):\\b", re.IGNORECASE)


def has_evidence(message: str | dict | None) -> bool:
    """Check whether a worker update carries concrete evidence."""
    if message is None:
        return False

    if isinstance(message, dict):
        keys = {"changed_file", "changed_files", "commands", "command", "result", "results",
                "reproduction", "test_failure", "blocking", "blocker", "artifact", "artifact_id"}
        return any(
            k in message and message[k]
            for k in keys
        ) or any(
            isinstance(v, list) and v for v in message.values() if isinstance(v, list)
        )

    if not isinstance(message, str):
        return False

    text = message.strip()
    if not text:
        return False

    if _CMD_RE.search(text):
        return True
    if _SYMBOL_RE.search(text) and any(
        marker in text.lower() for marker in ("path", "file", "changed", "repro", "failed", "artifact", "cmd", "command")
    ):
        return True
    if _PATH_RE.search(text):
        return True
    return False


def evaluate_worker_response(worker: WorkerLifecycle, message: str | dict | None) -> LifecycleAction:
    """Advance lifecycle state and return the policy action."""
    worker.turns += 1
    matched = has_evidence(message)
    worker.evidence_log.append(
        EvidenceEvent(
            worker_id=worker.worker_id,
            message="" if message is None else (message if isinstance(message, str) else str(message)),
            turn=worker.turns,
            has_evidence=matched,
        )
    )

    if matched:
        worker.evidence_free_turns = 0
        return LifecycleAction.CONTINUE

    worker.evidence_free_turns += 1
    if worker.evidence_free_turns == 1:
        return LifecycleAction.RETRY
    if worker.evidence_free_turns == 2 and not worker.replaced:
        # Replacement should be attempted immediately.
        worker.replaced = True
        worker.evidence_free_turns = 0
        return LifecycleAction.REPLACE
    if worker.evidence_free_turns >= 2 and worker.replaced:
        # Replacement already failed at least once with no evidence.
        return LifecycleAction.ESCALATE
    return LifecycleAction.RETRY
