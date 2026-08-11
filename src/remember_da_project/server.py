"""FastMCP server for remember_da_project."""

from typing import Optional
from fastmcp import FastMCP

from . import db

mcp = FastMCP(
    name="remember-da-project",
    instructions=(
        "Persistent memory for vibe coding sessions. "
        "Use get_session_context at the start of every session to load project state. "
        "Use upsert_map_entry to record what you discover about the codebase. "
        "Use add_task / update_task to track work across sessions."
    ),
)


# ---------------------------------------------------------------------------
# Project tools
# ---------------------------------------------------------------------------

@mcp.tool()
def init_project(path: str, name: str) -> dict:
    """Register a project by its absolute directory path. Idempotent."""
    return db.init_project(path, name)


@mcp.tool()
def init_and_fill_project(path: str, name: str) -> str:
    """
    Register a project (idempotent) then return a prompt instructing the agent
    to read the project's markdown files and populate tasks from them.

    The agent should read CLAUDE.md, *PLAN*.md, *DONE*.md, *TODO*.md, *TASK*.md
    (if they exist), extract tasks and context, then call add_task / update_task
    accordingly.
    """
    import glob as _glob

    db.init_project(path, name)

    patterns = [
        "CLAUDE.md", "claude.md",
        "*PLAN*.md", "*plan*.md",
        "*DONE*.md", "*done*.md",
        "*TODO*.md", "*todo*.md",
        "*TASK*.md", "*task*.md",
    ]
    seen: set[str] = set()
    found: list[str] = []
    for pattern in patterns:
        for p in _glob.glob(f"{path}/{pattern}"):
            if p not in seen:
                seen.add(p)
                found.append(p)
    found.sort(key=lambda p: __import__("os").path.getmtime(p), reverse=True)

    if not found:
        return (
            f"Project '{name}' registered at {path}. "
            "No markdown files (CLAUDE.md, *PLAN*.md, *DONE*.md, *TODO*.md, *TASK*.md) "
            "were found — nothing to import."
        )

    file_list = "\n".join(f"  - {p}" for p in found)
    existing = db.list_tasks(path)
    existing_titles = (
        "\n".join(f"  - [{t['status']}] {t['title']}" for t in existing)
        if existing
        else "  (none)"
    )

    return f"""Project '{name}' registered at {path}.

The following markdown files were found (newest first):
{file_list}

Please read each file above and extract every actionable task or work item.
For each task found:
- Call add_task(project_path="{path}", title=..., description=...) to create it.
- If the task is clearly done/completed, also call update_task(task_id=..., status="done").
- If it is in-progress, call update_task(task_id=..., status="in_progress").
- If it is blocked, call update_task(task_id=..., status="blocked").

Already-existing tasks (do not duplicate these):
{existing_titles}

After creating tasks:
- Extract any key project-level context (architecture decisions, conventions, important notes)
  and store them with set_note(project_path="{path}", key=..., value=...).
- Extract any mentions of specific files or modules with a clear purpose description and store
  them with upsert_map_entry(project_path="{path}", path=..., description=..., tags=..., notes=...)."""


@mcp.tool()
def get_project(project_path: str) -> Optional[dict]:
    """Get project metadata by absolute directory path."""
    return db.get_project(project_path)


@mcp.tool()
def list_projects() -> list[dict]:
    """
    List all registered projects with stats: task_count, active_task_count,
    map_entry_count, note_count, command_count. Use to discover known projects
    before calling get_session_context on a specific one.
    """
    return db.list_projects()


@mcp.tool()
def remove_project(project_path: str) -> bool:
    """Delete a project and ALL its data (tasks, map entries, commands, notes). Requires exact path."""
    return db.remove_project(project_path)


@mcp.tool()
def get_session_context(project_path: str) -> dict:
    """
    Load full project context for the current session.
    Auto-registers the project if not known.
    Returns: active tasks, commands, notes, and the 20 most recently updated map entries.
    Call this at the start of every session.
    """
    return db.get_session_context(project_path)


# ---------------------------------------------------------------------------
# Task tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_tasks(project_path: str, status: Optional[str] = None) -> list[dict]:
    """
    List tasks for a project. Optionally filter by status.
    Valid statuses: new, in_progress, done, blocked.
    """
    return db.list_tasks(project_path, status)


@mcp.tool()
def add_task(project_path: str, title: str, description: Optional[str] = None) -> dict:
    """Create a new task (status=new) for a project."""
    return db.add_task(project_path, title, description)


@mcp.tool()
def update_task(
    task_id: int,
    status: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[dict]:
    """
    Update a task's status, title, or description. Pass only the fields to change.
    Valid statuses: new, in_progress, done, blocked.
    """
    return db.update_task(task_id, status, title, description)


@mcp.tool()
def delete_task(task_id: int) -> bool:
    """Delete a task by ID."""
    return db.delete_task(task_id)


# ---------------------------------------------------------------------------
# Codebase map tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_map(project_path: str, query: str) -> list[dict]:
    """
    Full-text search across the codebase map (path, description, tags, notes).
    Use this to find what you already know about a file or topic before grepping.
    """
    return db.search_map(project_path, query)


@mcp.tool()
def list_map_entries(project_path: str, tag: Optional[str] = None) -> list[dict]:
    """List all codebase map entries, optionally filtered by tag."""
    return db.list_map_entries(project_path, tag)


@mcp.tool()
def get_map_entry(project_path: str, path: str) -> Optional[dict]:
    """Get a single codebase map entry by file/module path."""
    return db.get_map_entry(project_path, path)


@mcp.tool()
def upsert_map_entry(
    project_path: str,
    path: str,
    description: str,
    tags: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Add or update a codebase map entry.
    - path: relative file or module path (e.g. 'src/auth/jwt.py')
    - description: what this file/module does
    - tags: comma-separated tags (e.g. 'auth,jwt,security')
    - notes: freeform context, gotchas, patterns
    """
    return db.upsert_map_entry(project_path, path, description, tags, notes)


@mcp.tool()
def delete_map_entry(project_path: str, path: str) -> bool:
    """Delete a codebase map entry by file/module path."""
    return db.delete_map_entry(project_path, path)


# ---------------------------------------------------------------------------
# Command tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_commands(project_path: str) -> list[dict]:
    """List all named commands for a project (build, test, run, lint, etc.)."""
    return db.get_commands(project_path)


@mcp.tool()
def set_command(
    project_path: str,
    name: str,
    command: str,
    description: Optional[str] = None,
) -> dict:
    """Add or update a named command. E.g. name='build', command='make dev'."""
    return db.set_command(project_path, name, command, description)


@mcp.tool()
def delete_command(project_path: str, name: str) -> bool:
    """Delete a named command."""
    return db.delete_command(project_path, name)


# ---------------------------------------------------------------------------
# Note tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_notes(project_path: str) -> list[dict]:
    """List all key/value notes for a project."""
    return db.list_notes(project_path)


@mcp.tool()
def get_note(project_path: str, key: str) -> Optional[dict]:
    """Get a specific note by key."""
    return db.get_note(project_path, key)


@mcp.tool()
def set_note(project_path: str, key: str, value: str) -> dict:
    """Add or update a freeform note. E.g. key='orm', value='SQLAlchemy 2.x'."""
    return db.set_note(project_path, key, value)


@mcp.tool()
def delete_note(project_path: str, key: str) -> bool:
    """Delete a note by key."""
    return db.delete_note(project_path, key)


# ---------------------------------------------------------------------------
# Session checkpoint
# ---------------------------------------------------------------------------

@mcp.tool()
def save_session(project_path: str) -> str:
    """
    Prompt the agent to persist everything learned during the current session.
    Call this before ending a session to ensure progress is not lost.
    """
    tasks = db.list_tasks(project_path)
    task_summary = (
        "\n".join(f"  [{t['status']}] (id={t['id']}) {t['title']}" for t in tasks)
        if tasks else "  (none)"
    )

    return f"""Please save your session progress for project at {project_path}.

Current tasks in DB:
{task_summary}

Do all of the following that apply:

1. TASKS — for every task whose status changed during this session, call:
   update_task(task_id=..., status=...)
   Valid statuses: new, in_progress, done, blocked.
   If you started new work that has no task yet, call add_task(...) first.

2. CODEBASE MAP — for every file or module you read or modified, call:
   upsert_map_entry(project_path="{project_path}", path=<relative path>, description=..., tags=..., notes=...)
   Include gotchas, patterns, or anything a future session should know about that file.

3. NOTES — for any architectural decisions, conventions, or project-level context discovered, call:
   set_note(project_path="{project_path}", key=..., value=...)

Be thorough — this is the only record that will survive to the next session."""


# ---------------------------------------------------------------------------
# Web UI tool
# ---------------------------------------------------------------------------

@mcp.tool()
def get_web_ui_url(project_path: Optional[str] = None) -> dict:
    """
    Ensures the remember_da_project web UI is running, then returns its URL.
    Launches the web server in the background if it is not already running.
    Optionally includes a direct link to a specific project.
    """
    import subprocess
    import sys
    import socket

    base_url = "http://localhost:5000"

    # Check if the web UI is already listening on port 5000
    already_running = False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        already_running = s.connect_ex(("127.0.0.1", 5000)) == 0

    launched = False
    if not already_running:
        subprocess.Popen(
            [sys.executable, "-m", "remember_da_project.web"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        launched = True

    if project_path:
        from urllib.parse import urlencode
        url = f"{base_url}/?{urlencode({'path': project_path})}"
    else:
        url = base_url

    status = "launched" if launched else "already running"
    return {"url": url, "status": status}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
