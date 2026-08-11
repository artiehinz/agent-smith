from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tomllib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from agent_smith.integration import AGENTS_START, connect, disconnect, doctor
from tools.run_policy_dashboard import REPO_ROOT, _DashboardHandler, _resolve_static_file


def test_connect_preserves_existing_files_and_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# Existing\n\n- Keep me.\n", encoding="utf-8")
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text(
        "[features]\nmulti_agent = true\n",
        encoding="utf-8",
    )
    (tmp_path / ".gitignore").write_text(".venv/\n", encoding="utf-8")

    first = connect(tmp_path)
    second = connect(tmp_path)

    assert first["ok"] is True
    assert second["managed_files"] == first["managed_files"]
    agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "# Existing" in agents
    assert agents.count(AGENTS_START) == 1
    config = tomllib.loads((tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert config["features"]["multi_agent"] is True
    assert "agent_smith_reviewer" in config["agents"]
    assert (tmp_path / ".agents" / "skills" / "agent-smith" / "SKILL.md").is_file()
    assert doctor(tmp_path)["ok"] is True


def test_disconnect_preserves_modified_generated_file(tmp_path: Path) -> None:
    connect(tmp_path)
    role = tmp_path / ".codex" / "agents" / "agent-smith-explorer.toml"
    role.write_text(role.read_text(encoding="utf-8") + "# local change\n", encoding="utf-8")

    result = disconnect(tmp_path)

    assert ".codex/agents/agent-smith-explorer.toml" in result["preserved_modified"]
    assert role.is_file()
    assert AGENTS_START not in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert not (tmp_path / ".agent-smith" / "config.json").exists()


def test_connect_refuses_to_overwrite_modified_generated_file_without_force(tmp_path: Path) -> None:
    connect(tmp_path)
    role = tmp_path / ".codex" / "agents" / "agent-smith-explorer.toml"
    original = role.read_text(encoding="utf-8")
    role.write_text(original + "# local change\n", encoding="utf-8")

    with pytest.raises(ValueError, match="--force"):
        connect(tmp_path)

    assert role.read_text(encoding="utf-8").endswith("# local change\n")
    assert doctor(tmp_path)["ok"] is False
    connect(tmp_path, force=True)
    assert role.read_text(encoding="utf-8") == original
    assert doctor(tmp_path)["ok"] is True


def test_runtime_state_defaults_to_host_project(tmp_path: Path) -> None:
    code = "from core.paths import STATE_DIR; print(STATE_DIR)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
    )
    assert Path(result.stdout.strip()) == (tmp_path / ".agent-smith" / "runtime").resolve()


def test_dashboard_static_resolution_is_allowlisted() -> None:
    assert _resolve_static_file("/static/css/dashboard.css") == (REPO_ROOT / "static/css/dashboard.css").resolve()
    assert _resolve_static_file("/core/session/lifecycle.py") is None
    assert _resolve_static_file("/static/../../README.md") is None
    assert _resolve_static_file("/static/%2e%2e/%2e%2e/README.md") is None


def test_dashboard_serves_ui_but_not_repository_source() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/dashboard/index.html")
        response = connection.getresponse()
        assert response.status == 200
        assert b"Agent Smith" in response.read()
        connection.close()

        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/core/paths.py")
        response = connection.getresponse()
        assert response.status == 404
        response.read()
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_manifest_is_machine_readable(tmp_path: Path) -> None:
    connect(tmp_path)
    manifest = json.loads((tmp_path / ".agent-smith" / "config.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["managed_files"]


def test_policy_routes_import_without_site_packages() -> None:
    result = subprocess.run(
        [sys.executable, "-S", "-c", "from core.api_server.routes import policy_routes; print('ok')"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "ok"
