"""Database layer for remember_da_project."""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


DB_DIR = Path.home() / ".local" / "share" / "remember_da_project"
DB_PATH = DB_DIR / "memory.db"


def get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id         INTEGER PRIMARY KEY,
                path       TEXT UNIQUE NOT NULL,
                name       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY,
                project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title       TEXT NOT NULL,
                description TEXT,
                status      TEXT NOT NULL DEFAULT 'new',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS map_entries (
                id          INTEGER PRIMARY KEY,
                project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                path        TEXT NOT NULL,
                description TEXT NOT NULL,
                tags        TEXT,
                notes       TEXT,
                updated_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(project_id, path)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS map_fts USING fts5(
                path, description, tags, notes,
                content=map_entries,
                content_rowid=id
            );

            CREATE TABLE IF NOT EXISTS commands (
                id          INTEGER PRIMARY KEY,
                project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                command     TEXT NOT NULL,
                description TEXT,
                UNIQUE(project_id, name)
            );

            CREATE TABLE IF NOT EXISTS notes (
                id          INTEGER PRIMARY KEY,
                project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                key         TEXT NOT NULL,
                value       TEXT NOT NULL,
                UNIQUE(project_id, key)
            );

            -- FTS triggers
            CREATE TRIGGER IF NOT EXISTS map_entries_ai AFTER INSERT ON map_entries BEGIN
                INSERT INTO map_fts(rowid, path, description, tags, notes)
                VALUES (new.id, new.path, new.description, new.tags, new.notes);
            END;

            CREATE TRIGGER IF NOT EXISTS map_entries_ad AFTER DELETE ON map_entries BEGIN
                INSERT INTO map_fts(map_fts, rowid, path, description, tags, notes)
                VALUES ('delete', old.id, old.path, old.description, old.tags, old.notes);
            END;

            CREATE TRIGGER IF NOT EXISTS map_entries_au AFTER UPDATE ON map_entries BEGIN
                INSERT INTO map_fts(map_fts, rowid, path, description, tags, notes)
                VALUES ('delete', old.id, old.path, old.description, old.tags, old.notes);
                INSERT INTO map_fts(rowid, path, description, tags, notes)
                VALUES (new.id, new.path, new.description, new.tags, new.notes);
            END;
        """)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_project_id(conn: sqlite3.Connection, path: str) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM projects WHERE path = ?", (path,)
    ).fetchone()
    return row["id"] if row else None


# ---------------------------------------------------------------------------
# Project functions
# ---------------------------------------------------------------------------

def init_project(path: str, name: str) -> dict:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO projects (path, name) VALUES (?, ?)",
            (path, name),
        )
        row = conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
        return dict(row)


def get_project(path: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE path = ?", (path,)
        ).fetchone()
        return dict(row) if row else None


def remove_project(path: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM projects WHERE path = ?", (path,)
        )
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------

VALID_STATUSES = {"new", "in_progress", "done", "blocked"}


def list_tasks(project_path: str, status: Optional[str] = None) -> list[dict]:
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return []
        if status is not None:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE project_id = ? AND status = ? ORDER BY id",
                (project_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE project_id = ? ORDER BY id",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]


def add_task(
    project_path: str,
    title: str,
    description: Optional[str] = None,
) -> dict:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            raise ValueError(f"Project not found for path: {project_path}")
        cursor = conn.execute(
            "INSERT INTO tasks (project_id, title, description) VALUES (?, ?, ?)",
            (project_id, title, description),
        )
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)


def update_task(
    task_id: int,
    status: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[dict]:
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        new_status = status if status is not None else row["status"]
        new_title = title if title is not None else row["title"]
        new_description = description if description is not None else row["description"]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """UPDATE tasks
               SET status = ?, title = ?, description = ?, updated_at = ?
               WHERE id = ?""",
            (new_status, new_title, new_description, now, task_id),
        )
        updated = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(updated)


def delete_task(task_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Map entry functions
# ---------------------------------------------------------------------------

def search_map(project_path: str, query: str) -> list[dict]:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return []
        rows = conn.execute(
            """SELECT me.* FROM map_fts
               JOIN map_entries me ON map_fts.rowid = me.id
               WHERE me.project_id = ? AND map_fts MATCH ?
               ORDER BY me.updated_at DESC""",
            (project_id, query),
        ).fetchall()
        return [dict(row) for row in rows]


def list_map_entries(
    project_path: str,
    tag: Optional[str] = None,
) -> list[dict]:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return []
        if tag is not None:
            rows = conn.execute(
                """SELECT * FROM map_entries
                   WHERE project_id = ? AND tags LIKE ?
                   ORDER BY updated_at DESC""",
                (project_id, f"%{tag}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM map_entries WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]


def get_map_entry(project_path: str, path: str) -> Optional[dict]:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return None
        row = conn.execute(
            "SELECT * FROM map_entries WHERE project_id = ? AND path = ?",
            (project_id, path),
        ).fetchone()
        return dict(row) if row else None


def upsert_map_entry(
    project_path: str,
    path: str,
    description: str,
    tags: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            raise ValueError(f"Project not found for path: {project_path}")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """INSERT INTO map_entries (project_id, path, description, tags, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(project_id, path) DO UPDATE SET
                   description = excluded.description,
                   tags        = excluded.tags,
                   notes       = excluded.notes,
                   updated_at  = excluded.updated_at""",
            (project_id, path, description, tags, notes, now),
        )
        row = conn.execute(
            "SELECT * FROM map_entries WHERE project_id = ? AND path = ?",
            (project_id, path),
        ).fetchone()
        return dict(row)


def delete_map_entry(project_path: str, path: str) -> bool:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return False
        cursor = conn.execute(
            "DELETE FROM map_entries WHERE project_id = ? AND path = ?",
            (project_id, path),
        )
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Command functions
# ---------------------------------------------------------------------------

def get_commands(project_path: str) -> list[dict]:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return []
        rows = conn.execute(
            "SELECT * FROM commands WHERE project_id = ? ORDER BY name",
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def set_command(
    project_path: str,
    name: str,
    command: str,
    description: Optional[str] = None,
) -> dict:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            raise ValueError(f"Project not found for path: {project_path}")
        conn.execute(
            """INSERT INTO commands (project_id, name, command, description)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(project_id, name) DO UPDATE SET
                   command     = excluded.command,
                   description = excluded.description""",
            (project_id, name, command, description),
        )
        row = conn.execute(
            "SELECT * FROM commands WHERE project_id = ? AND name = ?",
            (project_id, name),
        ).fetchone()
        return dict(row)


def delete_command(project_path: str, name: str) -> bool:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return False
        cursor = conn.execute(
            "DELETE FROM commands WHERE project_id = ? AND name = ?",
            (project_id, name),
        )
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Note functions
# ---------------------------------------------------------------------------

def list_notes(project_path: str) -> list[dict]:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return []
        rows = conn.execute(
            "SELECT * FROM notes WHERE project_id = ? ORDER BY key",
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_note(project_path: str, key: str) -> Optional[dict]:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return None
        row = conn.execute(
            "SELECT * FROM notes WHERE project_id = ? AND key = ?",
            (project_id, key),
        ).fetchone()
        return dict(row) if row else None


def set_note(project_path: str, key: str, value: str) -> dict:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            raise ValueError(f"Project not found for path: {project_path}")
        conn.execute(
            """INSERT INTO notes (project_id, key, value)
               VALUES (?, ?, ?)
               ON CONFLICT(project_id, key) DO UPDATE SET
                   value = excluded.value""",
            (project_id, key, value),
        )
        row = conn.execute(
            "SELECT * FROM notes WHERE project_id = ? AND key = ?",
            (project_id, key),
        ).fetchone()
        return dict(row)


def delete_note(project_path: str, key: str) -> bool:
    with get_connection() as conn:
        project_id = _get_project_id(conn, project_path)
        if project_id is None:
            return False
        cursor = conn.execute(
            "DELETE FROM notes WHERE project_id = ? AND key = ?",
            (project_id, key),
        )
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Session context
# ---------------------------------------------------------------------------

def get_session_context(project_path: str) -> dict:
    # Auto-register project if unknown, using directory name as the project name.
    project = get_project(project_path)
    if project is None:
        name = Path(project_path).name
        project = init_project(project_path, name)

    with get_connection() as conn:
        project_id = project["id"]

        active_tasks = conn.execute(
            """SELECT * FROM tasks
               WHERE project_id = ? AND status IN ('new', 'in_progress', 'blocked')
               ORDER BY id""",
            (project_id,),
        ).fetchall()

        commands = conn.execute(
            "SELECT * FROM commands WHERE project_id = ? ORDER BY name",
            (project_id,),
        ).fetchall()

        notes = conn.execute(
            "SELECT * FROM notes WHERE project_id = ? ORDER BY key",
            (project_id,),
        ).fetchall()

        recent_map_entries = conn.execute(
            """SELECT * FROM map_entries
               WHERE project_id = ?
               ORDER BY updated_at DESC
               LIMIT 20""",
            (project_id,),
        ).fetchall()

    return {
        "project": project,
        "active_tasks": [dict(row) for row in active_tasks],
        "commands": [dict(row) for row in commands],
        "notes": [dict(row) for row in notes],
        "recent_map_entries": [dict(row) for row in recent_map_entries],
    }


# ---------------------------------------------------------------------------
# Module initialisation
# ---------------------------------------------------------------------------

init_db()
