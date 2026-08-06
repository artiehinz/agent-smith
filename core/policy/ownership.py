"""One-writer ownership controls for delegated work."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class OwnershipRecord:
    task_id: str
    owner: str
    scope: list[str] = field(default_factory=list)


class OwnershipLedger:
    """Keep a soft lock per canonical path symbol.

    The ledger is intentionally simple and optimistic. It prevents overlapping edit
    attempts inside a single process; persistent enforcement remains an
    orchestrator-level concern.
    """

    def __init__(self) -> None:
        self._by_path: dict[str, OwnershipRecord] = {}
        self._task_paths: defaultdict[str, set[str]] = defaultdict(set)

    def acquire(self, task_id: str, owner: str, path: str) -> bool:
        current = self._by_path.get(path)
        if current is None:
            self._by_path[path] = OwnershipRecord(task_id=task_id, owner=owner, scope=[path])
            self._task_paths[task_id].add(path)
            return True
        if current.task_id == task_id and current.owner == owner:
            self._task_paths[task_id].add(path)
            return True
        return False

    def release(self, task_id: str, owner: str | None = None, path: str | None = None) -> int:
        """Release locks for one path or all paths on task."""
        released = 0
        if path is not None:
            current = self._by_path.get(path)
            if current and current.task_id == task_id and (owner is None or current.owner == owner):
                self._by_path.pop(path, None)
                self._task_paths[task_id].discard(path)
                released += 1
            return released

        for p in list(self._task_paths.get(task_id, set())):
            current = self._by_path.get(p)
            if current and current.task_id == task_id and (owner is None or current.owner == owner):
                self._by_path.pop(p, None)
                self._task_paths[task_id].discard(p)
                released += 1
        return released

    def owner_of(self, path: str) -> str | None:
        item = self._by_path.get(path)
        return item.owner if item else None

    def can_edit(self, task_id: str, owner: str, path: str) -> bool:
        owner_record = self._by_path.get(path)
        return owner_record is None or (owner_record.task_id == task_id and owner_record.owner == owner)
