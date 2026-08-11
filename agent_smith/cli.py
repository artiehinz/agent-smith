"""Command line interface for connecting Agent Smith to projects."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .integration import connect, disconnect, doctor


def _print_doctor(result: dict[str, object]) -> None:
    for raw in result.get("checks", []):
        check = raw if isinstance(raw, dict) else {}
        label = str(check.get("status", "unknown")).upper().ljust(4)
        print(f"[{label}] {check.get('name')}: {check.get('detail')}")
    print("\nAgent Smith is ready." if result.get("ok") else "\nAgent Smith is not fully connected. Run `agent-smith connect .`.")


def _route(args: argparse.Namespace) -> int:
    from core.policy import RouteContext, classify_route, route_token_budget

    context = RouteContext(
        task_breadth=args.breadth,
        affected_packages=args.packages,
        uncertainty=args.uncertainty,
        verification_complexity=args.verification,
        independent_work_opportunities=args.parallelism,
        estimated_agent_overhead=args.overhead,
        route_hint=args.hint,
    )
    decision = classify_route(context)
    payload = {
        "route": decision.route.value,
        "score": decision.score,
        "override_applied": decision.override_applied,
        "rationale": decision.rationale,
        "details": decision.details,
        "token_budget": route_token_budget(decision.route.value).__dict__,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _dashboard(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    os.environ["AGENT_SMITH_PROJECT_ROOT"] = str(project)
    os.environ["AGENT_SMITH_STATE_DIR"] = str(project / ".agent-smith" / "runtime")
    from tools.run_policy_dashboard import run_server

    run_server(host=args.host, port=args.port)
    return 0


def _context(args: argparse.Namespace) -> int:
    path = Path(args.project).expanduser().resolve() / ".agent-smith" / "context.md"
    if not path.is_file():
        raise FileNotFoundError(f"Agent Smith project context not found: {path}; run connect first")
    if args.path_only:
        print(path)
    else:
        print(path.read_text(encoding="utf-8"), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-smith",
        description="Connect Agent Smith's multi-agent workflow to a Codex project.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("connect", "init"):
        command = subparsers.add_parser(name, help="install or update the repo-local Codex integration")
        command.add_argument("project", nargs="?", default=".")
        command.add_argument("--force", action="store_true", help="replace modified or unowned generated files")

    command = subparsers.add_parser("doctor", help="validate a connected project")
    command.add_argument("project", nargs="?", default=".")
    command.add_argument("--json", action="store_true", dest="as_json")

    command = subparsers.add_parser("disconnect", help="remove unmodified generated integration files")
    command.add_argument("project", nargs="?", default=".")

    command = subparsers.add_parser("context", help="show the connected project's durable context")
    command.add_argument("project", nargs="?", default=".")
    command.add_argument("--path", action="store_true", dest="path_only", help="print only the context file path")

    command = subparsers.add_parser("dashboard", help="run the optional local policy dashboard")
    command.add_argument("project", nargs="?", default=".")
    command.add_argument("--host", default="127.0.0.1")
    command.add_argument("--port", type=int, default=8000)

    command = subparsers.add_parser("route", help="classify a task using the policy engine")
    command.add_argument("--breadth", type=int, default=4)
    command.add_argument("--packages", type=int, default=1)
    command.add_argument("--uncertainty", type=int, default=3)
    command.add_argument("--verification", type=int, default=4)
    command.add_argument("--parallelism", type=int, default=1)
    command.add_argument("--overhead", type=int, default=1)
    command.add_argument("--hint", choices=("direct", "structured", "parallel"))

    subparsers.add_parser("headroom", help="show optional Headroom integration status and commands")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in {"connect", "init"}:
            result = connect(args.project, force=args.force)
            print(f"Connected Agent Smith {result['version']} to {result['project']} ({result['managed_files']} managed files).")
            print("Restart Codex in that project, then run `agent-smith doctor .`.")
            return 0
        if args.command == "doctor":
            result = doctor(args.project)
            if args.as_json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                _print_doctor(result)
            return 0 if result.get("ok") else 1
        if args.command == "disconnect":
            result = disconnect(args.project)
            print(f"Disconnected Agent Smith from {result['project']}.")
            if result["preserved_modified"]:
                print("Preserved modified generated files: " + ", ".join(result["preserved_modified"]))
            print("Preserved project-owned context: " + str(result["preserved_context"]))
            return 0
        if args.command == "context":
            return _context(args)
        if args.command == "route":
            return _route(args)
        if args.command == "dashboard":
            return _dashboard(args)
        if args.command == "headroom":
            status = doctor(".")
            headroom = next(item for item in status["checks"] if item["name"] == "Headroom")
            print(f"Headroom: {headroom['detail']}")
            print('Install: uv tool install --python 3.13 "headroom-ai[all]"')
            print("Use:     headroom wrap codex")
            print("Verify:  headroom doctor")
            print("Undo:    headroom unwrap codex")
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"agent-smith: {exc}", file=sys.stderr)
        return 2
    parser.error(f"unknown command: {args.command}")
    return 2
