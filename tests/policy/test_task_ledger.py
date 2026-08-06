"""Tests for policy task ledger persistence."""

from core.policy.task_ledger import init_ledger, new_task_id, upsert_task, get_task_ledger, record_task_event, task_events


def test_task_ledger_round_trip(tmp_path):
    db = tmp_path / "policy_ledger.sqlite"
    init_ledger(db)

    task_id = new_task_id("smoke")
    upsert_task(
        db,
        task_id=task_id,
        route="structured",
        owner_role="executor",
        status="open",
        metadata={"model": "gpt-5.6-luna"},
    )
    record_task_event(db, task_id, "started", {"status": "started"})

    row = get_task_ledger(db, task_id)
    assert row is not None
    assert row["route"] == "structured"
    assert row["owner_role"] == "executor"
    assert row["metadata"]["model"] == "gpt-5.6-luna"

    events = task_events(db, task_id)
    assert len(events) == 1
    assert events[0]["kind"] == "started"
