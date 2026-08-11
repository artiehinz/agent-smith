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

- Use `$agent-smith` for non-trivial implementation, debugging, review, or repository-wide work.
- Choose the smallest effective topology: work directly when one owner is faster; delegate only independent, bounded work.
- Keep one writer per worktree. Parallelize read-only discovery and isolated work, then verify all handoffs in the primary thread.
- Treat subagent output as evidence, not completion. The primary agent owns integration, tests, and the final verdict.
{AGENTS_END}"""

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

    planned_targets = [root / relative for relative in ROLE_CONFIGS]
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

    for relative, content in ROLE_CONFIGS.items():
        target = root / relative
        _write_text(target, content)
        managed_files[relative] = _sha256(target)

    for target in _copy_skill(root):
        relative = target.relative_to(root).as_posix()
        managed_files[relative] = _sha256(target)

    _write_text(ignore_path, ignore_content)

    manifest = {
        "schema_version": 1,
        "agent_smith_version": __version__,
        "project_root": str(root),
        "managed_files": managed_files,
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

    config = root / ".codex" / "config.toml"
    config_ok = False
    config_detail = "missing"
    if config.is_file():
        try:
            parsed = tomllib.loads(config.read_text(encoding="utf-8"))
            configured = parsed.get("agents", {}) if isinstance(parsed, dict) else {}
            config_ok = all(name in configured for name in (
                "agent_smith_explorer",
                "agent_smith_executor",
                "agent_smith_tester",
                "agent_smith_reviewer",
            ))
            config_detail = "valid with Agent Smith roles" if config_ok else "valid TOML, roles missing"
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
    return {"ok": True, "project": str(root), "removed": removed, "preserved_modified": preserved}
