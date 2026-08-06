"""Execution policy package for local planning and worker governance.

These modules intentionally avoid external dependencies so they can be imported
early and used as decision helpers across the CLI, MCP, and dashboard layers.
"""

from .route_classifier import (
    Route,
    RouteContext,
    RouteDecision,
    classify_route,
)
from .preflight import (
    PreflightIntent,
    PreflightResult,
    generate_preflight_marker,
    parse_preflight_output,
    preflight_prompt,
    preflight_report,
)
from .agent_backends import (
    AgentBackend,
    BackendDecision,
    choose_backend,
    explicit_worker_args,
    prefer_explicit_workers,
    should_disable_delegation,
)
from .token_limits import (
    TokenBudget,
    TokenBudgetError,
    route_token_budget,
    clamp_token_budget,
)
from .task_ledger import (
    TaskLedgerConfig,
    init_ledger,
    upsert_task,
    record_task_event,
    get_task_ledger,
    list_open_tasks,
    task_events,
    new_task_id,
)
from .worker_packets import (
    PacketScope,
    WorkerPacket,
    as_delta_message,
)
from .worker_lifecycle import (
    EvidenceEvent,
    LifecycleAction,
    WorkerLifecycle,
    evaluate_worker_response,
)
from .tool_batching import (
    ToolCall,
    independent_reads,
    needs_worker_for_parallel,
)
from .context_scout import (
    ScoutDecision,
    should_run_context_scout,
)
from .ownership import (
    OwnershipRecord,
    OwnershipLedger,
)
from .executor_tester_repair import (
    DefectType,
    RepairLoopState,
    cycle_once,
    defect_destination,
    should_continue_repair,
)

__all__ = [
    "Route",
    "RouteContext",
    "RouteDecision",
    "classify_route",
    "PacketScope",
    "WorkerPacket",
    "as_delta_message",
    "PreflightIntent",
    "PreflightResult",
    "generate_preflight_marker",
    "parse_preflight_output",
    "preflight_prompt",
    "preflight_report",
    "AgentBackend",
    "BackendDecision",
    "choose_backend",
    "explicit_worker_args",
    "prefer_explicit_workers",
    "should_disable_delegation",
    "TokenBudget",
    "TokenBudgetError",
    "route_token_budget",
    "clamp_token_budget",
    "TaskLedgerConfig",
    "init_ledger",
    "upsert_task",
    "record_task_event",
    "get_task_ledger",
    "list_open_tasks",
    "task_events",
    "new_task_id",
    "EvidenceEvent",
    "LifecycleAction",
    "WorkerLifecycle",
    "evaluate_worker_response",
    "DefectType",
    "RepairLoopState",
    "cycle_once",
    "defect_destination",
    "should_continue_repair",
    "ToolCall",
    "independent_reads",
    "needs_worker_for_parallel",
    "ScoutDecision",
    "should_run_context_scout",
    "OwnershipRecord",
    "OwnershipLedger",
]
