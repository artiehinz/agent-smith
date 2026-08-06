"""Tests for one-writer ownership policy."""

from core.policy.ownership import OwnershipLedger


def test_ownership_acquire_and_release_path():
    ledger = OwnershipLedger()
    assert ledger.acquire(task_id="task-1", owner="owner-a", path="src/auth.py") is True
    assert ledger.owner_of("src/auth.py") == "owner-a"
    assert ledger.can_edit(task_id="task-1", owner="owner-a", path="src/auth.py") is True
    assert ledger.can_edit(task_id="task-2", owner="owner-b", path="src/auth.py") is False
    assert ledger.release(task_id="task-1", owner="owner-a", path="src/auth.py") == 1
    assert ledger.can_edit(task_id="task-2", owner="owner-b", path="src/auth.py") is True
