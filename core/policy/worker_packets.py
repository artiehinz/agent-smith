"""Bounded, delta-friendly worker packets for delegated execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any


class PacketRole(str, Enum):
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    EXPLORATION = "exploration"


@dataclass(frozen=True)
class PacketScope:
    read: list[str] = field(default_factory=list)
    write: list[str] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)


@dataclass
class WorkerPacket:
    task_id: str
    role: str = PacketRole.IMPLEMENTATION.value
    outcome: dict[str, Any] = field(default_factory=dict)
    scope: PacketScope = field(default_factory=PacketScope)
    acceptance: list[str] = field(default_factory=list)
    context_refs: list[str] = field(default_factory=list)
    return_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role
        return data

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)


def as_delta_message(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Return a delta-only packet update.

    For each key in ``update`` only values that changed from base are retained.
    This is designed to keep worker follow-up messages compact.
    """
    delta: dict[str, Any] = {}
    for key, value in update.items():
        if key not in base or base[key] != value:
            delta[key] = value
    return delta


def clamp_token_budget(
    initial_tokens: int = 0,
    progress_tokens: int = 0,
    followup_tokens: int = 0,
    final_tokens: int = 0,
) -> tuple[int, int, int, int]:
    """Clamp planned budgets to the reference plan ranges."""
    return (
        max(300, min(initial_tokens, 500)),
        max(80, min(progress_tokens, 160)),
        max(120, min(followup_tokens, 220)),
        max(250, min(final_tokens, 420)),
    )
