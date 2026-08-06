"""Tests for policy defaults attached to scan session state."""

import core.session as scan_session


def test_session_start_includes_route_policy():
    current = scan_session.start("https://example.local", depth="standard", scope=[])
    policy = current.get("policy")
    assert isinstance(policy, dict)
    assert policy["route"] in {"direct", "structured", "parallel"}
    assert "token_budget" in policy
    assert "task_hard" in policy["token_budget"]
    assert policy["policy_engine"] == "route_classifier_v1"
