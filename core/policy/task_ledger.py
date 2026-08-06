"""SQLite-backed task ledger used by policy execution traces."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4
import time


SCHEMA = """
CREATE TABLE IF NOT EXISTS task_ledger (
    task_id TEXT PRIMARY KEY,
    route TEXT NOT NULL,
    owner_role TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    started_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(task_id) REFERENCES task_ledger(task_id)
);
"""


@dataclass(frozen=True)
class TaskLedgerConfig:
    db_path: Path
    require_metadata: bool = True


def init_ledger(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(Path(db_path))


def upsert_task(
    db_path: str | Path,
    task_id: str,
    *,
    route: str,
    owner_role: str,
    status: str = "open",
    metadata: dict[str, Any] | None = None,
) -> None:
    init_ledger(db_path)
    payload = json.dumps(metadata or {}, sort_keys=True)
    now = time.time()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO task_ledger(task_id, route, owner_role, status, metadata_json, started_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                route = excluded.route,
                owner_role = excluded.owner_role,
                status = excluded.status,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (task_id, route, owner_role, status, payload, now, now),
        )
        conn.commit()


def record_task_event(
    db_path: str | Path,
    task_id: str,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> None:
    init_ledger(db_path)
    now = time.time()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO task_events(task_id, kind, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, kind, json.dumps(payload or {}, sort_keys=True), now),
        )
        conn.execute(
            "UPDATE task_ledger SET updated_at = ?, status = ? WHERE task_id = ?",
            (now, kind, task_id),
        )
        conn.commit()


def get_task_ledger(db_path: str | Path, task_id: str) -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT task_id, route, owner_role, status, metadata_json, started_at, updated_at
            FROM task_ledger WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        if not row:
            return None
        route, owner_role, status, metadata_json, started_at, updated_at = row[1], row[2], row[3], row[4], row[5], row[6]
        return {
            "task_id": row[0],
            "route": route,
            "owner_role": owner_role,
            "status": status,
            "metadata": json.loads(metadata_json) if metadata_json else {},
            "started_at": started_at,
            "updated_at": updated_at,
        }


def list_open_tasks(db_path: str | Path) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT task_id, route, owner_role, status, updated_at
            FROM task_ledger
            ORDER BY updated_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def task_events(db_path: str | Path, task_id: str) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT kind, payload_json, created_at FROM task_events WHERE task_id = ? ORDER BY id ASC",
            (task_id,),
        ).fetchall()
        out = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                payload = {}
            out.append(
                {
                    "kind": row["kind"],
                    "payload": payload,
                    "created_at": row["created_at"],
                }
            )
        return out


def new_task_id(prefix: str = "task") -> str:
    return f"{prefix}-{uuid4().hex[:10]}"
