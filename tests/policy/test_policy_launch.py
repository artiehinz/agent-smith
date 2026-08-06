"""Tests for policy launch decision contracts and launch-time persistence."""
from core import session as scan_session
from core.policy.agent_backends import AgentBackend, BackendDecision
from core.policy.model_attestation import ModelAttestation, ModelSpec
from core.policy.preflight import PreflightIntent, PreflightResult
from core.policy.task_ledger import task_events
from core.session import lifecycle


def test_policy_launch_plan_includes_route_hint_and_explicit_command() -> None:
    current = scan_session.start("https://example.local", depth="standard", scope=[])
    policy = current["policy"]
    policy["route"] = "parallel"
    policy["route_hint"] = "parallel"

    decision = lifecycle.policy_launch_plan(
        "executor",
        intended_model="gpt-5.6-luna",
        intended_effort="medium",
    )

    assert decision["enabled"] is True
    assert decision["route"] == "parallel"
    assert decision["route_hint"] == "parallel"
    assert decision["selected_backend"] == AgentBackend.EXPLICIT.value
    assert isinstance(decision["command"], list)

    required_keys = {
        "enabled",
        "role",
        "route",
        "route_hint",
        "selected_backend",
        "fallback_backend",
        "requires_approval",
        "fail_closed",
        "block_delegation",
        "reason",
        "command",
    }
    assert required_keys.issubset(decision.keys())


def test_policy_launch_enforcement_blocks_fail_closed_delegation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    current = scan_session.start("https://example.local", depth="standard", scope=[])

    events: list[dict] = []

    def fake_record_task_event(task_db, task_id, kind, payload):  # type: ignore[override]
        events.append({"task_id": task_id, "kind": kind, "payload": payload})

    monkeypatch.setattr(lifecycle, "record_task_event", fake_record_task_event)
    decision = lifecycle.evaluate_policy_launch(
        "executor",
        intended_model="gpt-5.6-luna",
        intended_effort="medium",
        explicit_worker_available=False,
    )

    assert decision["enabled"] is True
    assert decision["status"] == "blocked"
    assert decision["action"] == "blocked"
    assert decision["block_delegation"] is True
    assert any(e["kind"] == "delegation_blocked" for e in events)
    assert current["policy"]["backend_decisions"]["executor"]["status"] == "blocked"


def test_policy_launch_enforcement_requires_approval_when_backend_requires_approval(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    current = scan_session.start("https://example.local", depth="standard", scope=[])
    events: list[dict] = []

    def fake_record_task_event(task_db, task_id, kind, payload):  # type: ignore[override]
        events.append({"task_id": task_id, "kind": kind, "payload": payload})

    def fake_choose_backend(
        role: str,
        intended_model: str,
        intended_effort: str,
        *,
        attestation: ModelAttestation | None = None,
        explicit_worker_available: bool = True,
    ) -> BackendDecision:
        return BackendDecision(
            role=role,
            selected_backend=AgentBackend.NATIVE,
            fallback_backend=AgentBackend.EXPLICIT if explicit_worker_available else None,
            fail_closed=False,
            requires_approval=True,
            reason="test requires approval",
        )

    monkeypatch.setattr(lifecycle, "record_task_event", fake_record_task_event)
    monkeypatch.setattr(lifecycle, "choose_backend", fake_choose_backend)
    decision = lifecycle.evaluate_policy_launch(
        "executor",
        intended_model="gpt-5.6-luna",
        intended_effort="medium",
    )

    assert decision["status"] == "needs_approval"
    assert decision["action"] == "needs_approval"
    assert decision["requires_approval"] is True
    assert decision["block_delegation"] is False
    assert any(e["kind"] == "delegation_needs_approval" for e in events)
    assert current["policy"]["backend_decisions"]["executor"]["status"] == "needs_approval"


def test_enforce_launch_contract_blocks_and_denies_launch(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    scan_session.start("https://example.local", depth="standard", scope=[])

    def fake_record_task_event(task_db, task_id, kind, payload):  # type: ignore[override]
        return None

    def fake_resolve_launch_contract(*_args, **_kwargs):
        return {
            "ok": False,
            "launch_authorized": False,
            "enabled": True,
            "role": "executor",
            "route": "direct",
            "route_hint": "direct",
            "selected_backend": "native_subagent",
            "fallback_backend": None,
            "requires_approval": False,
            "fail_closed": True,
            "block_delegation": True,
            "reason": "tests",
            "status": "blocked",
            "action": "blocked",
            "command": None,
        }

    monkeypatch.setattr(lifecycle, "resolve_launch_contract", fake_resolve_launch_contract)
    monkeypatch.setattr(lifecycle, "record_task_event", fake_record_task_event)

    result = lifecycle.enforce_launch_contract("executor", intended_model="gpt-5.6-luna", intended_effort="medium")

    assert result["ok"] is False
    assert result["action"] == "blocked"
    assert result["launch"] is False
    assert result["status"] == "blocked"


def test_enforce_launch_contract_authorizes_and_allows_launch(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    scan_session.start("https://example.local", depth="standard", scope=[])

    def fake_resolve_launch_contract(*_args, **_kwargs):
        return {
            "ok": True,
            "launch_authorized": True,
            "enabled": True,
            "role": "executor",
            "route": "direct",
            "route_hint": "direct",
            "selected_backend": "native_subagent",
            "fallback_backend": None,
            "requires_approval": False,
            "fail_closed": False,
            "block_delegation": False,
            "reason": "tests",
            "status": "authorized",
            "action": "authorized",
            "command": None,
        }

    monkeypatch.setattr(lifecycle, "resolve_launch_contract", fake_resolve_launch_contract)
    result = lifecycle.enforce_launch_contract("executor", intended_model="gpt-5.6-luna", intended_effort="medium")

    assert result["ok"] is True
    assert result["action"] == "authorized"
    assert result["launch"] is True
    assert result["status"] == "authorized"


def test_enforce_launch_contract_reports_needs_approval(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    scan_session.start("https://example.local", depth="standard", scope=[])

    def fake_resolve_launch_contract(*_args, **_kwargs):
        return {
            "ok": False,
            "launch_authorized": False,
            "enabled": True,
            "role": "executor",
            "route": "direct",
            "route_hint": "direct",
            "selected_backend": "native_subagent",
            "fallback_backend": None,
            "requires_approval": True,
            "fail_closed": False,
            "block_delegation": False,
            "reason": "tests",
            "status": "needs_approval",
            "action": "needs_approval",
            "command": None,
        }

    monkeypatch.setattr(lifecycle, "resolve_launch_contract", fake_resolve_launch_contract)
    result = lifecycle.enforce_launch_contract("executor", intended_model="gpt-5.6-luna", intended_effort="medium")

    assert result["ok"] is False
    assert result["action"] == "needs_approval"
    assert result["launch"] is False
    assert result["requires_approval"] is True
    assert result["status"] == "needs_approval"


def test_enforce_launch_contract_without_active_session_returns_blocked(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    def fake_resolve_launch_contract(*_args, **_kwargs):
        return {
            "ok": False,
            "launch_authorized": False,
            "enabled": False,
            "role": None,
            "route": None,
            "route_hint": None,
            "selected_backend": None,
            "fallback_backend": None,
            "requires_approval": False,
            "fail_closed": False,
            "block_delegation": False,
            "reason": "no active session",
            "status": "unknown",
            "action": None,
        }

    monkeypatch.setattr(lifecycle, "resolve_launch_contract", fake_resolve_launch_contract)
    result = lifecycle.enforce_launch_contract("executor", intended_model="gpt-5.6-luna", intended_effort="medium")

    assert result["ok"] is False
    assert result["action"] == "blocked"
    assert result["launch"] is False
    assert result["status"] == "unknown"


def test_enforce_and_execute_launch_invokes_executor_only_when_authorized(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    scan_session.start("https://example.local", depth="standard", scope=[])
    calls: list[dict[str, object]] = []

    def fake_resolve_launch_contract(*_args, **_kwargs):
        return {
            "ok": True,
            "launch_authorized": True,
            "enabled": True,
            "role": "executor",
            "route": "direct",
            "route_hint": "direct",
            "selected_backend": "native_subagent",
            "fallback_backend": None,
            "requires_approval": False,
            "fail_closed": False,
            "block_delegation": False,
            "reason": "tests",
            "status": "authorized",
            "action": "authorized",
            "command": None,
        }

    def launch_executor(*, contract, **_kwargs) -> dict[str, object]:
        calls.append({"contract": contract})
        return {"launched": True}

    monkeypatch.setattr(lifecycle, "resolve_launch_contract", fake_resolve_launch_contract)
    result = lifecycle.enforce_and_execute_launch(
        "executor",
        intended_model="gpt-5.6-luna",
        intended_effort="medium",
        launch_executor=launch_executor,
    )

    assert result["ok"] is True
    assert result["launch"] is True
    assert result["execution"] == {"launched": True}
    assert calls == [{"contract": result["contract"]}]


def test_enforce_and_execute_launch_does_not_invoke_executor_when_blocked(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    scan_session.start("https://example.local", depth="standard", scope=[])
    calls: list[dict[str, object]] = []

    def fake_resolve_launch_contract(*_args, **_kwargs):
        return {
            "ok": False,
            "launch_authorized": False,
            "enabled": True,
            "role": "executor",
            "route": "direct",
            "route_hint": "direct",
            "selected_backend": "native_subagent",
            "fallback_backend": None,
            "requires_approval": False,
            "fail_closed": True,
            "block_delegation": True,
            "reason": "tests",
            "status": "blocked",
            "action": "blocked",
            "command": None,
        }

    def launch_executor(*_kwargs) -> dict[str, object]:
        calls.append({})
        return {"launched": True}

    monkeypatch.setattr(lifecycle, "resolve_launch_contract", fake_resolve_launch_contract)
    result = lifecycle.enforce_and_execute_launch(
        "executor",
        intended_model="gpt-5.6-luna",
        intended_effort="medium",
        launch_executor=launch_executor,
    )

    assert result["ok"] is False
    assert result["launch"] is False
    assert result["action"] == "blocked"
    assert calls == []


def test_session_start_auto_preflight_populates_policy_blocks(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    monkeypatch.setattr(lifecycle, "_policy_preflight_targets", lambda _: ("executor",))

    marker = "policy-autoprobe-marker"

    def fake_run_preflight_probe(intent: PreflightIntent, _marker: str) -> PreflightResult:
        return PreflightResult(
            intent=intent,
            marker=marker,
            raw_output="mode=medium",
            status="match",
            actual_role=intent.role,
            actual_model=intent.model,
            actual_effort=intent.effort,
            actual_sandbox=intent.sandbox,
        )

    monkeypatch.setattr(lifecycle, "run_preflight_probe", fake_run_preflight_probe)
    current = scan_session.start("https://example.local", depth="standard", scope=[], scan_mode="benchmark")
    policy = current["policy"]

    preflight = policy.get("preflight", {})
    backend_decisions = policy.get("backend_decisions", {})
    preflight_state = policy.get("policy_preflight_state", {})
    expected_route = policy.get("route")
    expected_route_hint = policy.get("route_hint")

    assert isinstance(preflight, dict)
    assert "executor" in preflight
    assert isinstance(backend_decisions, dict)
    assert "executor" in backend_decisions
    assert backend_decisions["executor"]["route"] == expected_route
    assert backend_decisions["executor"]["route_hint"] == expected_route_hint
    assert "command" in backend_decisions["executor"]
    assert preflight_state.get("mode") == "session_start"
    assert preflight_state.get("roles") == ["executor"]
    assert preflight_state.get("status") == "completed"

    events = task_events(lifecycle._POLICY_LEDGER_DB, policy["ledger_id"])
    assert any(event["kind"] == "preflight" for event in events)
