"""Tests for evidence-based worker lifecycle policy."""

from core.policy.worker_lifecycle import LifecycleAction, WorkerLifecycle, evaluate_worker_response


def test_worker_lifecycle_escalates_after_repeated_no_evidence():
    lifecycle = WorkerLifecycle(worker_id="executor-1")
    assert evaluate_worker_response(lifecycle, "I am investigating") == LifecycleAction.RETRY
    assert evaluate_worker_response(lifecycle, "still checking") == LifecycleAction.REPLACE
    assert lifecycle.replaced is True
    assert evaluate_worker_response(lifecycle, "no output") == LifecycleAction.RETRY
    assert evaluate_worker_response(lifecycle, "still nothing") == LifecycleAction.ESCALATE


def test_worker_lifecycle_accepts_evidence_then_continues():
    lifecycle = WorkerLifecycle(worker_id="executor-2")
    assert evaluate_worker_response(lifecycle, None) == LifecycleAction.RETRY
    assert evaluate_worker_response(lifecycle, {"changed_file": "src/main.py"}) == LifecycleAction.CONTINUE
