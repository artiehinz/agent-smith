"""SQLite-backed task handoff ledger."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS task_ledger (
            task_id TEXT PRIMARY KEY,
            route TEXT NOT NULL,
            owner_role TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            route_hint TEXT,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES task_ledger(task_id)
        );
        CREATE INDEX IF NOT EXISTS idx_task_ledger_status ON task_ledger(status);
        CREATE INDEX IF NOT EXISTS idx_task_ledger_owner_role ON task_ledger(owner_role);
        CREATE INDEX IF NOT EXISTS idx_task_ledger_updated_at ON task_ledger(updated_at);
        CREATE INDEX IF NOT EXISTS idx_task_events_task_id ON task_events(task_id);
        """
    )


def init_ledger(path: str | Path) -> None:
    """Create or migrate the policy task ledger schema."""
    with _connect(path) as connection:
        _ensure_schema(connection)
        connection.commit()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_loads(payload: str | None) -> dict[str, Any]:
    if not payload:
        return {}
    try:
        loaded = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if isinstance(loaded, dict):
        return loaded
    return {}


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload or {}, ensure_ascii=False)


def upsert_task(
    path: str | Path,
    task_id: str,
    *,
    route: str,
    owner_role: str,
    status: str,
    metadata: dict[str, Any] | None = None,
    route_hint: str | None = None,
) -> None:
    now = _timestamp()
    with _connect(path) as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO task_ledger (task_id, route, owner_role, status, created_at, updated_at, route_hint, metadata)
            VALUES (:task_id, :route, :owner_role, :status, :timestamp, :timestamp, :route_hint, :metadata)
            ON CONFLICT(task_id) DO UPDATE SET
                route=excluded.route,
                owner_role=excluded.owner_role,
                status=excluded.status,
                updated_at=excluded.updated_at,
                route_hint=COALESCE(excluded.route_hint, task_ledger.route_hint),
                metadata=excluded.metadata
            """,
            {
                "task_id": task_id,
                "route": route,
                "owner_role": owner_role,
                "status": status,
                "timestamp": now,
                "route_hint": route_hint,
                "metadata": _json_dumps(metadata or {}),
            },
        )
        connection.commit()


def record_task_event(
    path: str | Path,
    task_id: str,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> None:
    with _connect(path) as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO task_events (task_id, kind, payload, created_at)
            VALUES (:task_id, :kind, :payload, :created_at)
            """,
            {
                "task_id": task_id,
                "kind": kind,
                "payload": _json_dumps(payload or {}),
                "created_at": _timestamp(),
            },
        )
        connection.commit()


def get_task_ledger(path: str | Path, task_id: str) -> dict[str, Any] | None:
    with _connect(path) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT * FROM task_ledger WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "task_id": row["task_id"],
            "route": row["route"],
            "owner_role": row["owner_role"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "route_hint": row["route_hint"],
            "metadata": _json_loads(row["metadata"]),
        }


def task_events(path: str | Path, task_id: str, limit: int | None = None) -> list[dict[str, Any]]:
    if not task_id:
        return []
    with _connect(path) as connection:
        _ensure_schema(connection)
        query = "SELECT * FROM task_events WHERE task_id = ? ORDER BY id ASC"
        rows = connection.execute(query, (task_id,)).fetchall()
        events = [
            {
                "id": row["id"],
                "task_id": row["task_id"],
                "kind": row["kind"],
                "payload": _json_loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        if limit is not None and limit > 0:
            return events[-limit:]
        return events


def list_open_tasks(
    path: str | Path,
    *,
    status: str | None = None,
    owner_role: str | None = None,
    route: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    with _connect(path) as connection:
        _ensure_schema(connection)
        query_parts = ["SELECT * FROM task_ledger"]
        where: list[str] = []
        params: list[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if owner_role:
            where.append("owner_role = ?")
            params.append(owner_role)
        if route:
            where.append("route = ?")
            params.append(route)
        if since:
            where.append("updated_at >= ?")
            params.append(since)
        if until:
            where.append("updated_at <= ?")
            params.append(until)
        if where:
            query_parts.append("WHERE " + " AND ".join(where))
        query_parts.append("ORDER BY updated_at DESC")
        if limit > 0:
            query_parts.append("LIMIT ?")
            params.append(limit)
        if offset > 0:
            query_parts.append("OFFSET ?")
            params.append(offset)
        query = " ".join(query_parts)
        rows = connection.execute(query, tuple(params)).fetchall()
        return [
            {
                "task_id": row["task_id"],
                "route": row["route"],
                "owner_role": row["owner_role"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "route_hint": row["route_hint"],
                "metadata": _json_loads(row["metadata"]),
            }
            for row in rows
        ]
