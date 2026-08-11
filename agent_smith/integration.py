"""Install and validate Agent Smith's repo-local Codex integration."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import __version__

AGENTS_START = "<!-- agent-smith:start -->"
AGENTS_END = "<!-- agent-smith:end -->"
CODEX_START = "# agent-smith:start"
CODEX_END = "# agent-smith:end"
IGNORE_START = "# agent-smith:start"
IGNORE_END = "# agent-smith:end"

AGENTS_BLOCK = f"""{AGENTS_START}
## Agent Smith orchestration

- Apply Agent Smith to every repository modification. Use the direct route for small changes and `$agent-smith` explicitly when orchestration would help.
- Read `.agent-smith/context.md` before non-trivial work; treat current source and tests as authoritative when it is stale.
- Choose the smallest effective topology: work directly when one owner is faster; delegate only independent, bounded work.
- Keep one writer per worktree. Parallelize read-only discovery and isolated work, then verify all handoffs in the primary thread.
- Treat subagent output as evidence, not completion. The primary agent owns integration, tests, and the final verdict.
- Before finishing any material change, run a documentation delta review. Update project context and relevant docs when behavior, architecture, setup, commands, or invariants changed; otherwise state that no documentation update was needed. Never create timestamp-only or status-only churn.
{AGENTS_END}"""

UNIX_HOOK_COMMAND = 'python3 "$(git rev-parse --show-toplevel)/.codex/hooks/agent-smith.py"'
WINDOWS_HOOK_COMMAND = (
    'powershell -NoProfile -ExecutionPolicy Bypass -Command '
    '"$root = git rev-parse --show-toplevel; python (Join-Path $root \'.codex/hooks/agent-smith.py\')"'
)

CODEX_BLOCK = f'''{CODEX_START}
[agents.agent_smith_explorer]
description = "Read-only repository discovery and impact analysis for a bounded question."
config_file = "agents/agent-smith-explorer.toml"

[agents.agent_smith_executor]
description = "Bounded implementation in an explicitly assigned, non-overlapping ownership scope."
config_file = "agents/agent-smith-executor.toml"

[agents.agent_smith_tester]
description = "Independent verification focused on observable behavior and regression evidence."
config_file = "agents/agent-smith-tester.toml"

[agents.agent_smith_reviewer]
description = "Read-only review for correctness, security, regressions, and missing verification."
config_file = "agents/agent-smith-reviewer.toml"

[[hooks.SessionStart]]
matcher = "^(startup|resume|clear|compact)$"

[[hooks.SessionStart.hooks]]
type = "command"
command = {json.dumps(UNIX_HOOK_COMMAND)}
command_windows = {json.dumps(WINDOWS_HOOK_COMMAND)}
statusMessage = "Loading Agent Smith project context"
additionalContextLimit = 4000
timeout = 10

[[hooks.SubagentStart]]

[[hooks.SubagentStart.hooks]]
type = "command"
command = {json.dumps(UNIX_HOOK_COMMAND)}
command_windows = {json.dumps(WINDOWS_HOOK_COMMAND)}
statusMessage = "Loading Agent Smith project context"
additionalContextLimit = 4000
timeout = 10

[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = {json.dumps(UNIX_HOOK_COMMAND)}
command_windows = {json.dumps(WINDOWS_HOOK_COMMAND)}
timeout = 10

[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = {json.dumps(UNIX_HOOK_COMMAND)}
command_windows = {json.dumps(WINDOWS_HOOK_COMMAND)}
statusMessage = "Checking Agent Smith documentation delta"
timeout = 15
{CODEX_END}'''

ROLE_CONFIGS = {
    ".codex/agents/agent-smith-explorer.toml": '''model_reasoning_effort = "medium"
sandbox_mode = "read-only"
developer_instructions = """Stay read-only. Answer the assigned question with concise, source-backed findings, affected paths, material uncertainty, and recommended next checks. Do not broaden scope or implement changes."""
''',
    ".codex/agents/agent-smith-executor.toml": '''model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
developer_instructions = """Implement only the assigned bounded outcome. Respect declared ownership boundaries, preserve unrelated changes, run focused validation, and return changed paths, evidence, risks, and any remaining uncertainty. Do not commit or push."""
''',
    ".codex/agents/agent-smith-tester.toml": '''model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
developer_instructions = """Verify the assigned behavior independently. Prefer observable tests and realistic failure cases. Do not repair product code unless explicitly assigned. Report exact commands, results, regressions, and evidence gaps."""
''',
    ".codex/agents/agent-smith-reviewer.toml": '''model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = """Review the assigned change without editing. Prioritize correctness, security, data loss, concurrency, public contracts, and missing tests. Report findings by severity with file and line evidence; say explicitly when no material findings remain."""
''',
}

HOOK_SCRIPT = r'''"""Agent Smith lifecycle hook installed into a connected project."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path

MAX_CONTEXT_BYTES = 16 * 1024
INTEGRATION_PREFIXES = (
    ".agent-smith/runtime/",
    ".agents/skills/agent-smith/",
    ".codex/agents/agent-smith-",
    ".codex/hooks/agent-smith.py",
)
INTEGRATION_FILES = {".agent-smith/config.json", ".codex/config.toml", ".gitignore", "AGENTS.md"}
DOC_SUFFIXES = {".md", ".mdx", ".rst", ".adoc", ".txt"}


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, separators=(",", ":")))


def project_root(cwd: str | None) -> Path:
    candidate = Path(cwd or ".").expanduser().resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        return candidate


def file_signature(root: Path, relative: str) -> str:
    path = root / relative
    try:
        stat = path.stat()
        if not path.is_file():
            return f"other:{stat.st_size}:{stat.st_mtime_ns}"
        if stat.st_size > 4 * 1024 * 1024:
            return f"large:{stat.st_size}:{stat.st_mtime_ns}"
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "missing"


def working_state(root: Path) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True,
            text=True,
            timeout=8,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    state: dict[str, str] = {}
    for line in result.stdout.splitlines():
        status = line[:2]
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"').replace("\\", "/")
        state[path] = f"{status}:{file_signature(root, path)}"
    return state


def baseline_path(root: Path, payload: dict[str, object]) -> Path:
    identity = f"{payload.get('session_id', '')}:{payload.get('turn_id', '')}"
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return root / ".agent-smith" / "runtime" / "hook-baselines" / f"{key}.json"


def save_baseline(root: Path, payload: dict[str, object]) -> None:
    path = baseline_path(root, payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(working_state(root), sort_keys=True), encoding="utf-8")
    emit({"continue": True})


def load_baseline(root: Path, payload: dict[str, object]) -> dict[str, str] | None:
    path = baseline_path(root, payload)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {str(key): str(value) for key, value in raw.items()} if isinstance(raw, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def clear_baseline(root: Path, payload: dict[str, object]) -> None:
    try:
        baseline_path(root, payload).unlink()
    except OSError:
        pass


def is_material(path: str) -> bool:
    if path in INTEGRATION_FILES or path.startswith(INTEGRATION_PREFIXES):
        return False
    lowered = path.lower()
    if lowered.startswith("docs/") or Path(lowered).suffix in DOC_SUFFIXES:
        return False
    return True


def load_context(root: Path, event: str) -> None:
    context_path = root / ".agent-smith" / "context.md"
    try:
        raw = context_path.read_bytes()[:MAX_CONTEXT_BYTES]
        context = raw.decode("utf-8", errors="replace")
    except OSError:
        context = "Project context is missing. Re-run `agent-smith connect .`."
    reminder = (
        "Agent Smith is connected. Use this compact project memory for repository work, "
        "but prefer current source and tests if it conflicts. Before finishing a material "
        "change, review documentation impact and update context/docs only for durable changes."
    )
    emit({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": f"{reminder}\n\n{context}",
        }
    })


def stop(root: Path, payload: dict[str, object]) -> None:
    if payload.get("stop_hook_active"):
        clear_baseline(root, payload)
        emit({"continue": True})
        return
    current = working_state(root)
    baseline = load_baseline(root, payload)
    changed = current if baseline is None else {
        path: current.get(path, "missing")
        for path in current.keys() | baseline.keys()
        if current.get(path) != baseline.get(path)
    }
    material = [path for path in sorted(changed) if is_material(path)]
    if not material:
        clear_baseline(root, payload)
        emit({"continue": True})
        return
    preview = ", ".join(material[:8])
    if len(material) > 8:
        preview += f", and {len(material) - 8} more"
    emit({
        "decision": "block",
        "reason": (
            "Agent Smith final documentation delta gate: material repository changes were "
            f"detected ({preview}). Review whether behavior, architecture, setup, commands, "
            "invariants, or durable decisions changed. If so, update `.agent-smith/context.md` "
            "and the relevant project documentation now. If not, explicitly confirm that no "
            "documentation update is needed, then finish. Do not create timestamp-only or "
            "status-only documentation churn."
        ),
    })


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be a JSON object")
        root = project_root(str(payload.get("cwd") or "."))
        event = payload.get("hook_event_name")
        if event in {"SessionStart", "SubagentStart"}:
            load_context(root, str(event))
        elif event == "UserPromptSubmit":
            save_baseline(root, payload)
        elif event == "Stop":
            stop(root, payload)
        else:
            emit({"continue": True})
        return 0
    except Exception as exc:  # Hooks must fail open instead of breaking repository work.
        emit({"continue": True, "systemMessage": f"Agent Smith hook warning: {exc}"})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

GENERATED_FILES = {
    **ROLE_CONFIGS,
    ".codex/hooks/agent-smith.py": HOOK_SCRIPT,
}

CONTEXT_MAX_BYTES = 16 * 1024


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    required: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "required": self.required,
        }


def _managed_pattern(start: str, end: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?:^|\n){re.escape(start)}\n.*?\n{re.escape(end)}(?=\n|$)",
        flags=re.DOTALL,
    )


def _replace_managed_block(existing: str, block: str, start: str, end: str) -> str:
    if (start in existing) != (end in existing):
        raise ValueError(f"managed block is malformed: expected both {start!r} and {end!r}")
    cleaned = _managed_pattern(start, end).sub("", existing).strip()
    return f"{cleaned}\n\n{block.strip()}\n" if cleaned else f"{block.strip()}\n"


def _remove_managed_block(existing: str, start: str, end: str) -> str:
    if (start in existing) != (end in existing):
        raise ValueError(f"managed block is malformed: expected both {start!r} and {end!r}")
    return _managed_pattern(start, end).sub("", existing).strip() + ("\n" if existing.strip() else "")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.agent-smith.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _skill_files(project: Path) -> list[tuple[Path, Path]]:
    source = Path(__file__).resolve().parent / "templates" / "agent-smith"
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError(f"Agent Smith skill template is missing: {source}")
    destination = project / ".agents" / "skills" / "agent-smith"
    files: list[tuple[Path, Path]] = []
    for source_file in source.rglob("*"):
        if not source_file.is_file():
            continue
        target = destination / source_file.relative_to(source)
        files.append((source_file, target))
    return files


def _copy_skill(project: Path) -> list[Path]:
    written: list[Path] = []
    for source_file, target in _skill_files(project):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target)
        written.append(target)
    return written


def _validate_toml(content: str, path: Path) -> None:
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"refusing to write invalid TOML to {path}: {exc}") from exc


def _context_template(root: Path) -> str:
    candidates = (
        "README.md",
        "CONTRIBUTING.md",
        "docs/README.md",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "requirements.txt",
        "Makefile",
        "justfile",
    )
    detected = [relative for relative in candidates if (root / relative).is_file()]
    docs_map = "\n".join(f"- `{relative}`" for relative in detected) or "- Add authoritative project documents and manifests here."
    return f"""# {root.name} project context

This is durable, compact project memory for Agent Smith and Codex. Keep it factual, under 200 lines and 16 KiB, and update it only when durable project knowledge changes. Current source, tests, and explicit user instructions remain authoritative.

## Purpose and scope

- Describe what this project does and what is out of scope.

## Architecture and component map

- Add the important components, boundaries, and data flow.

## Commands and verification

- Add canonical setup, run, lint, test, build, and release commands.

## Invariants and constraints

- Add compatibility, security, data, ownership, and operational constraints.

## Current focus and open risks

- Add only active, durable context that would change how the next task is solved.

## Durable decisions

- Keep the latest useful decisions; remove superseded or temporary status notes.

## Documentation map

{docs_map}
"""


def connect(project: str | Path = ".", *, force: bool = False) -> dict[str, object]:
    """Connect Agent Smith to a project without replacing existing project guidance."""
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project directory does not exist: {root}")

    managed_files: dict[str, str] = {}
    agents_path = root / "AGENTS.md"
    agents_existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    agents_content = _replace_managed_block(agents_existing, AGENTS_BLOCK, AGENTS_START, AGENTS_END)

    config_path = root / ".codex" / "config.toml"
    config_existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    config_content = _replace_managed_block(config_existing, CODEX_BLOCK, CODEX_START, CODEX_END)
    _validate_toml(config_content, config_path)

    ignore_path = root / ".gitignore"
    ignore_existing = ignore_path.read_text(encoding="utf-8") if ignore_path.exists() else ""
    ignore_block = f"{IGNORE_START}\n.agent-smith/runtime/\n{IGNORE_END}"
    ignore_content = _replace_managed_block(ignore_existing, ignore_block, IGNORE_START, IGNORE_END)

    manifest_path = root / ".agent-smith" / "config.json"
    previous_managed: dict[str, str] = {}
    if manifest_path.is_file():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_managed = previous.get("managed_files", {})
        if isinstance(raw_managed, dict):
            previous_managed = {str(key): str(value) for key, value in raw_managed.items()}

    planned_targets = [root / relative for relative in GENERATED_FILES]
    planned_targets.extend(target for _source, target in _skill_files(root))
    conflicts: list[str] = []
    for target in planned_targets:
        if not target.is_file():
            continue
        relative = target.relative_to(root).as_posix()
        expected = previous_managed.get(relative)
        if expected is None or _sha256(target) != expected:
            conflicts.append(relative)
    if conflicts and not force:
        raise ValueError(
            "refusing to overwrite modified or unowned generated files: "
            + ", ".join(conflicts)
            + "; rerun connect with --force to replace them"
        )

    # All conflict and syntax checks have passed; project writes start here.
    _write_text(agents_path, agents_content)
    _write_text(config_path, config_content)

    for relative, content in GENERATED_FILES.items():
        target = root / relative
        _write_text(target, content)
        managed_files[relative] = _sha256(target)

    for target in _copy_skill(root):
        relative = target.relative_to(root).as_posix()
        managed_files[relative] = _sha256(target)

    _write_text(ignore_path, ignore_content)

    context_path = root / ".agent-smith" / "context.md"
    if not context_path.exists():
        _write_text(context_path, _context_template(root))

    manifest = {
        "schema_version": 2,
        "agent_smith_version": __version__,
        "project_root": str(root),
        "managed_files": managed_files,
        "context_file": ".agent-smith/context.md",
        "runtime_dir": ".agent-smith/runtime",
        "headroom": "optional",
    }
    _write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {
        "ok": True,
        "project": str(root),
        "version": __version__,
        "managed_files": len(managed_files),
    }


def _command_version(command: str) -> tuple[bool, str]:
    executable = shutil.which(command)
    if not executable:
        return False, "not found on PATH"
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"found at {executable}, but version check failed: {exc}"
    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[0] if output else executable
    return result.returncode == 0, detail


def doctor(project: str | Path = ".") -> dict[str, object]:
    root = Path(project).expanduser().resolve()
    checks: list[Check] = []
    checks.append(Check("project", "pass" if root.is_dir() else "fail", str(root)))

    agents = root / "AGENTS.md"
    agents_text = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    agents_ok = AGENTS_START in agents_text and AGENTS_END in agents_text
    checks.append(Check("AGENTS.md", "pass" if agents_ok else "fail", "managed guidance present" if agents_ok else "run connect"))

    skill = root / ".agents" / "skills" / "agent-smith" / "SKILL.md"
    checks.append(Check("skill", "pass" if skill.is_file() else "fail", str(skill)))

    context = root / ".agent-smith" / "context.md"
    context_size = context.stat().st_size if context.is_file() else 0
    context_ok = context.is_file() and context_size <= CONTEXT_MAX_BYTES
    if not context.is_file():
        context_detail = "missing; run connect"
    elif context_size > CONTEXT_MAX_BYTES:
        context_detail = f"{context_size} bytes; compact below {CONTEXT_MAX_BYTES}"
    else:
        context_detail = f"{context_size} bytes; durable project memory ready"
    checks.append(Check("project context", "pass" if context_ok else "fail", context_detail))

    config = root / ".codex" / "config.toml"
    config_ok = False
    config_detail = "missing"
    if config.is_file():
        try:
            parsed = tomllib.loads(config.read_text(encoding="utf-8"))
            configured = parsed.get("agents", {}) if isinstance(parsed, dict) else {}
            hooks = parsed.get("hooks", {}) if isinstance(parsed, dict) else {}
            roles_ok = all(name in configured for name in (
                "agent_smith_explorer",
                "agent_smith_executor",
                "agent_smith_tester",
                "agent_smith_reviewer",
            ))
            hooks_ok = isinstance(hooks, dict) and all(
                name in hooks for name in ("SessionStart", "SubagentStart", "UserPromptSubmit", "Stop")
            )
            config_ok = roles_ok and hooks_ok
            if config_ok:
                config_detail = "valid with Agent Smith roles and lifecycle hooks"
            elif not roles_ok:
                config_detail = "valid TOML, roles missing"
            else:
                config_detail = "valid TOML, lifecycle hooks missing"
        except (OSError, tomllib.TOMLDecodeError) as exc:
            config_detail = f"invalid: {exc}"
    checks.append(Check("Codex config", "pass" if config_ok else "fail", config_detail))

    manifest = root / ".agent-smith" / "config.json"
    manifest_ok = False
    manifest_detail = str(manifest)
    if manifest.is_file():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            managed = payload.get("managed_files", {})
            mismatches: list[str] = []
            if not isinstance(managed, dict) or not managed:
                mismatches.append("managed file list missing")
            else:
                for relative, expected_hash in managed.items():
                    target = root / str(relative)
                    if not target.is_file() or _sha256(target) != str(expected_hash):
                        mismatches.append(str(relative))
            manifest_ok = not mismatches
            manifest_detail = "generated files match manifest" if manifest_ok else "missing or modified: " + ", ".join(mismatches)
        except (OSError, json.JSONDecodeError) as exc:
            manifest_detail = f"invalid: {exc}"
    checks.append(Check("manifest", "pass" if manifest_ok else "fail", manifest_detail))

    codex_ok, codex_detail = _command_version("codex")
    checks.append(Check("Codex CLI", "pass" if codex_ok else "warn", codex_detail, required=False))
    headroom_ok, headroom_detail = _command_version("headroom")
    checks.append(Check("Headroom", "pass" if headroom_ok else "skip", headroom_detail, required=False))

    ok = all(check.status == "pass" for check in checks if check.required)
    return {
        "ok": ok,
        "project": str(root),
        "version": __version__,
        "checks": [check.as_dict() for check in checks],
    }


def disconnect(project: str | Path = ".") -> dict[str, object]:
    """Remove only generated files that still match the recorded manifest."""
    root = Path(project).expanduser().resolve()
    manifest_path = root / ".agent-smith" / "config.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Agent Smith manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    managed = manifest.get("managed_files", {})
    removed: list[str] = []
    preserved: list[str] = []
    if isinstance(managed, dict):
        for relative, expected_hash in managed.items():
            target = root / str(relative)
            if not target.is_file():
                continue
            if _sha256(target) != expected_hash:
                preserved.append(str(relative))
                continue
            target.unlink()
            removed.append(str(relative))

    for path, start, end in (
        (root / "AGENTS.md", AGENTS_START, AGENTS_END),
        (root / ".codex" / "config.toml", CODEX_START, CODEX_END),
        (root / ".gitignore", IGNORE_START, IGNORE_END),
    ):
        if not path.is_file():
            continue
        updated = _remove_managed_block(path.read_text(encoding="utf-8"), start, end)
        _write_text(path, updated)

    manifest_path.unlink()
    for directory in (
        root / ".agents" / "skills" / "agent-smith" / "agents",
        root / ".agents" / "skills" / "agent-smith" / "references",
        root / ".agents" / "skills" / "agent-smith",
        root / ".codex" / "agents",
        root / ".agent-smith",
    ):
        try:
            directory.rmdir()
        except OSError:
            pass
    return {
        "ok": True,
        "project": str(root),
        "removed": removed,
        "preserved_modified": preserved,
        "preserved_context": str(root / ".agent-smith" / "context.md"),
    }
