"""Shared filesystem paths for code assets and project-local runtime state."""

from __future__ import annotations

import os
from pathlib import Path

INSTALL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.environ.get("AGENT_SMITH_PROJECT_ROOT", Path.cwd())).expanduser().resolve()
STATE_DIR = Path(
    os.environ.get("AGENT_SMITH_STATE_DIR", PROJECT_ROOT / ".agent-smith" / "runtime")
).expanduser().resolve()

# Compatibility name for code that needs checked-in dashboard or skill assets.
REPO_ROOT = INSTALL_ROOT
