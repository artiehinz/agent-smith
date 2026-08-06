"""Tests for bounded worker packet contracts."""

from core.policy.worker_packets import PacketScope, WorkerPacket, as_delta_message, clamp_token_budget


def test_worker_packet_round_trip():
    packet = WorkerPacket(
        task_id="auth-42",
        outcome={"result": "pending"},
        scope=PacketScope(read=["src/auth/**"], write=["src/auth/auth_service.py"]),
        acceptance=["Race condition reproduced before fix"],
        context_refs=["cx://symbol/AuthService.refreshToken"],
    )
    assert packet.to_dict()["task_id"] == "auth-42"
    assert packet.to_json().count("task_id") == 1


def test_as_delta_message_only_changes_values():
    base = {"status": "open", "notes": "A"}
    delta = as_delta_message(base, {"status": "open", "notes": "B", "new": "C"})
    assert "status" not in delta
    assert delta["notes"] == "B"
    assert delta["new"] == "C"


def test_clamp_token_budget_defaults_to_reference_bounds():
    budgets = clamp_token_budget(initial_tokens=1000, progress_tokens=10, followup_tokens=0, final_tokens=5000)
    assert budgets == (500, 160, 220, 420)
