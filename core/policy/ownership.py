"""Simple single-writer ownership bookkeeping."""
from __future__ import annotations

from dataclasses import dataclass, field


class OwnershipError(RuntimeError):
    """Raised when ownership cannot be assigned."""


def normalize_owner(owner: str | None) -> str:
    return (owner or "").strip().lower()


def scope_key(resource: str | None) -> str:
    return (resource or "").strip().lower()


@dataclass
class OwnershipState:
    owner: str
    resources: set[str] = field(default_factory=set)


@dataclass
class OwnershipLedger:
    owners: dict[str, str] = field(default_factory=dict)

    def can_assign_writer(self, resource: str, owner: str) -> bool:
        normalized_owner = normalize_owner(owner)
        normalized_resource = scope_key(resource)
        if not normalized_owner:
            return False
        if not normalized_resource:
            return False
        existing = self.owners.get(normalized_resource)
        return existing is None or existing == normalized_owner

    def acquire(self, resource: str, owner: str) -> bool:
        if not self.can_assign_writer(resource, owner):
            return False
        self.owners[scope_key(resource)] = normalize_owner(owner)
        return True

    def release(self, resource: str, owner: str) -> bool:
        normalized_resource = scope_key(resource)
        normalized_owner = normalize_owner(owner)
        if self.owners.get(normalized_resource) != normalized_owner:
            return False
        del self.owners[normalized_resource]
        return True

    def owner_for_resource(self, resource: str) -> str | None:
        return self.owners.get(scope_key(resource))


_GLOBAL_LEDGER = OwnershipLedger()


def can_assign_writer(resource: str, owner: str, ledger: OwnershipLedger | None = None) -> bool:
    return (ledger or _GLOBAL_LEDGER).can_assign_writer(resource, owner)


def owner_for_resource(resource: str, ledger: OwnershipLedger | None = None) -> str | None:
    return (ledger or _GLOBAL_LEDGER).owner_for_resource(resource)

