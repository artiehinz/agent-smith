"""Policy route should be one-task scoped."""

from core import session as scan_session
from core.session import limits
from core.policy.task_ledger import init_ledger, upsert_task, record_task_event, task_events
from core.session import lifecycle


def test_route_override_resets_after_complete():
    current = scan_session.start("https://example.local", depth="standard", scope=[])
    assert isinstance(current.get("policy"), dict)

    policy = current["policy"]
    policy["route"] = "direct"
    policy["route_hint"] = "direct"
    policy["override_applied"] = True

    completed = scan_session.complete("ok")
    assert isinstance(completed.get("policy"), dict)
    completed_policy = completed["policy"]

    assert completed_policy.get("route_hint") is None
    assert completed_policy.get("override_applied") is False
    assert "route" in completed_policy
    assert completed_policy.get("token_budget")


def test_route_completion_event_records_outcome_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    init_ledger(lifecycle._POLICY_LEDGER_DB)

    current = scan_session.start("https://example.local", depth="standard", scope=[])
    policy = current["policy"]
    policy["route"] = "parallel"
    policy["route_hint"] = "parallel"
    policy["override_applied"] = True
    task_id = "policy-xyz"
    upsert_task(
        lifecycle._POLICY_LEDGER_DB,
        task_id=task_id,
        route=policy["route"],
        owner_role="orchestrator",
        status="open",
        metadata={"route_hint": policy.get("route_hint")},
    )
    record_task_event(
        lifecycle._POLICY_LEDGER_DB,
        task_id=task_id,
        kind="started",
        payload={"route": policy["route"]},
    )
    policy["ledger_id"] = task_id

    completed = scan_session.complete("route outcome smoke test")
    events = task_events(lifecycle._POLICY_LEDGER_DB, task_id)

    completed_events = [event for event in events if event["kind"] == "completed"]
    assert completed_events, "completion event should be emitted when policy is tracked"
    completed_payload = completed_events[0]["payload"]
    assert completed_payload["route"] == "parallel"
    assert completed_payload["route_hint"] == "parallel"
    assert completed_payload["route_reset_applied"] is True
    assert isinstance(completed.get("policy"), dict)
    assert completed_payload["route_after_reset"] == completed["policy"]["route"]
    assert completed_payload["route_reset_source"] == "completion"


def test_limit_stop_records_route_outcome_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    init_ledger(lifecycle._POLICY_LEDGER_DB)

    current = scan_session.start("https://example.local", depth="standard", scope=[])
    policy = current["policy"]
    policy["route"] = "direct"
    policy["route_hint"] = "direct"
    policy["override_applied"] = True
    task_id = "policy-limit-xyz"
    upsert_task(
        lifecycle._POLICY_LEDGER_DB,
        task_id=task_id,
        route=policy["route"],
        owner_role="orchestrator",
        status="open",
        metadata={"route_hint": policy.get("route_hint")},
    )
    record_task_event(
        lifecycle._POLICY_LEDGER_DB,
        task_id=task_id,
        kind="started",
        payload={"route": policy["route"]},
    )
    policy["ledger_id"] = task_id

    scan_session._flush()
    message = limits._stop("limit_reached", "tests: synthetic limit hit")
    assert message == "tests: synthetic limit hit"
    assert current["status"] == "limit_reached"

    events = task_events(lifecycle._POLICY_LEDGER_DB, task_id)
    completed_events = [event for event in events if event["kind"] == "completed"]
    assert completed_events, "completion event should be emitted when hard limits stop execution"
    completed_payload = completed_events[0]["payload"]
    assert completed_payload["route_reset_applied"] is True
    assert completed_payload["status"] == "limit_reached"
    assert completed_payload["route"] == "direct"
    assert completed_payload["route_hint"] == "direct"
    assert completed_payload["route_after_reset"] == lifecycle._default_route_policy("standard", [])["route"]
    assert completed_payload["route_reset_source"] == "limit_reached"
