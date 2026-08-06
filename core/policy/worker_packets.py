"""Worker packet schema and compact delta helpers."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class PacketScope:
    read: list[str] = field(default_factory=list)
    write: list[str] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)


@dataclass
class WorkerPacket:
    task_id: str
    role: str
    outcome: str
    scope: PacketScope
    acceptance: list[str] = field(default_factory=list)
    context_refs: list[str] = field(default_factory=list)
    return_fields: list[str] = field(default_factory=list)


def as_delta_message(base: dict[str, Any] | None, update: dict[str, Any]) -> dict[str, Any]:
    """Return only changed keys from ``update`` relative to ``base``."""
    base = base or {}
    output: dict[str, Any] = {}
    for key, value in update.items():
        if key not in base:
            output[key] = value
            continue
        if isinstance(base.get(key), dict) and isinstance(value, dict):
            nested = as_delta_message(base.get(key, {}), value)
            if nested:
                output[key] = nested
            continue
        if base.get(key) != value:
            output[key] = value
    return output


def build_worker_packet(
    *,
    task_id: str,
    role: str,
    outcome: str,
    scope: PacketScope | dict[str, list[str]] | None = None,
    acceptance: list[str] | None = None,
    context_refs: list[str] | None = None,
    return_fields: list[str] | None = None,
    protected: list[str] | None = None,
    token_budget: int | None = None,
) -> dict[str, Any]:
    packet_scope = scope
    if isinstance(packet_scope, dict):
        packet_scope = PacketScope(
            read=list(packet_scope.get("read", [])),
            write=list(packet_scope.get("write", [])),
            protected=list(packet_scope.get("protected", [])),
        )
    if packet_scope is None:
        packet_scope = PacketScope(
            read=[],
            write=[],
            protected=list(protected or []),
        )

    packet = WorkerPacket(
        task_id=task_id,
        role=role,
        outcome=outcome,
        scope=packet_scope,
        acceptance=list(acceptance or []),
        context_refs=list(context_refs or []),
        return_fields=list(return_fields or []),
    )
    payload = asdict(packet)
    if token_budget is not None:
        payload["token_budget"] = token_budget
    return payload

