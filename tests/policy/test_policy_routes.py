"""Tests for policy API route helpers."""
import asyncio
import json

from core.api_server.routes import policy_routes as routes
from core.policy import PreflightIntent, PreflightResult
from core import session as scan_session
from core.session import lifecycle


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_normalize_preflight_role_accepts_plan_synonyms() -> None:
    assert routes._normalize_preflight_role("executor") == "executor"
    assert routes._normalize_preflight_role("security-review") == "security review"
    assert routes._normalize_preflight_role("security_review") == "security review"
    assert routes._normalize_preflight_role("EXPLORER") == "explorer"


def test_normalize_preflight_role_rejects_unknown() -> None:
    assert routes._normalize_preflight_role("builder") is None
    assert routes._normalize_preflight_role(" ") is None


def test_normalize_pref_bool_supports_strings() -> None:
    assert routes._normalize_pref_bool(True) is True
    assert routes._normalize_pref_bool(False) is False
    assert routes._normalize_pref_bool("true") is True
    assert routes._normalize_pref_bool("off") is False
    assert routes._normalize_pref_bool(None, default=True) is True


def test_attestation_payload_records_expected_marker() -> None:
    intent = PreflightIntent(role="executor", model="gpt-5.6-luna", effort="medium")
    result = PreflightResult(
        intent=intent,
        marker="expected-marker",
        raw_output="marker: observed-marker\nrole: executor\nmodel: gpt-5.6-luna\neffort: medium",
        actual_role="executor",
        actual_model="gpt-5.6-luna",
        actual_effort="medium",
        actual_sandbox="read_only",
    )
    payload = routes._attestation_payload(result, marker_expected="expected-marker")
    assert payload["marker_expected"] == "expected-marker"
    assert payload["status"] == "mismatch"


def test_update_policy_field_accepts_intent_role_fallback() -> None:
    policy: dict[str, dict[str, object]] = {}
    routes._update_policy_field(
        policy,
        "preflight",
        {
            "intent": {"role": "executor"},
            "status": "match",
            "marker": "m1",
            "marker_expected": "m1",
        },
    )
    assert policy["preflight"]["executor"]["status"] == "match"


def test_api_run_policy_preflight_manual_mode_records_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(routes, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    monkeypatch.setenv("SMITH_DISABLE_SESSION_PRELIGHT", "1")

    current = scan_session.start("https://example.local", depth="standard", scope=[])
    assert isinstance(current.get("policy"), dict)

    # No explicit monkeypatch for parse path needed here because we exercise manual mode
    response = _run(
        routes.api_run_policy_preflight(
            {
                "role": "executor",
                "model": "gpt-5.6-luna",
                "effort": "medium",
                "raw_output": "marker: m1\nrole: executor\nmodel: gpt-5.6-luna\neffort: medium\nsandbox: read_only\n",
                "sandbox": "read_only",
            }
        )
    )
    body = json.loads(response.body)

    assert body["ok"] is True
    assert body["mode"] == "manual"
    assert body["status"] == "match"

    policy = scan_session.get()["policy"]
    assert policy["preflight"]["executor"]["mode"] == "manual"
    assert policy["policy_preflight_state"]["mode"] == "manual"
    assert policy["policy_preflight_state"]["roles"] == ["executor"]


def test_api_run_policy_preflight_auto_mode_records_policy_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(routes, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    monkeypatch.setattr(lifecycle, "_POLICY_LEDGER_DB", tmp_path / "policy_task_ledger.sqlite")
    monkeypatch.setenv("SMITH_DISABLE_SESSION_PRELIGHT", "1")

    scan_session.start("https://example.local", depth="standard", scope=[])

    marker = "auto-marker"

    def fake_run_preflight_probe(intent: PreflightIntent, _marker: str) -> PreflightResult:
        return PreflightResult(
            intent=intent,
            marker=marker,
            raw_output="auto",
            status="match",
            actual_role=intent.role,
            actual_model=intent.model,
            actual_effort=intent.effort,
            actual_sandbox=intent.sandbox,
        )

    monkeypatch.setattr(routes, "run_preflight_probe", fake_run_preflight_probe)

    response = _run(
        routes.api_run_policy_preflight(
            {
                "role": "executor",
                "model": "gpt-5.6-luna",
                "effort": "medium",
            }
        )
    )
    body = json.loads(response.body)

    assert body["ok"] is True
    assert body["mode"] == "auto"
    assert body["policy_preflight_state"]["mode"] == "auto"
    assert body["preflight"]["status"] == "match"
