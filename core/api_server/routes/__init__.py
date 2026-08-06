"""Dashboard HTTP routes (package facade)."""
from __future__ import annotations

from ._common import router, _wake_smith_if_idle  # noqa: F401

from .policy_routes import (  # noqa: E402,F401
    api_policy,
    api_policy_tasks,
    api_policy_task,
    api_policy_preflight,
    api_run_policy_preflight,
    api_policy_launch_plan,
    api_set_policy_route,
    api_set_policy_repair,
)

__all__ = [
    "router",
    "_wake_smith_if_idle",
    "api_policy",
    "api_policy_tasks",
    "api_policy_task",
    "api_policy_preflight",
    "api_policy_launch_plan",
    "api_run_policy_preflight",
    "api_set_policy_route",
    "api_set_policy_repair",
]
