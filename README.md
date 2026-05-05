# remember-da-project

SQLite-backed MCP server for persistent memory across vibe coding sessions. Tracks tasks, codebase knowledge, commands, and notes — all stored in a single local file with zero server setup.

## Why

Vibe coding on large codebases wastes tokens re-discovering architecture and task state at the start of every session. This server gives your AI agent persistent memory across sessions with minimal friction.

**vs kanban-mcp:**
- SQLite only — no DB server, single file at `~/.local/share/remember_da_project/memory.db`
- Codebase map with full-text search — the gap kanban-mcp leaves open
- Session hook that auto-injects context at session start
- Simple web UI for at-a-glance project state

---

## Install

```bash
pip install -e /path/to/remember_da_project
```

This registers three CLI entry points: `remember-da-server`, `remember-da-hook`, `remember-da-web`.

---

## MCP Server Setup

Add to your MCP config (Claude Code, OpenCode, Mistral, or any MCP-compatible tool):

```json
{
  "mcpServers": {
    "remember-da-project": {
      "type": "stdio",
      "command": "remember-da-server",
      "args": []
    }
  }
}
```

If `remember-da-server` isn't on PATH (e.g. installed in a venv), use the absolute path:

```bash
which remember-da-server
```

**Usage pattern:** at the start of each session, call `get_session_context` with the project's absolute path. The server's instructions remind the agent to do this automatically.

---

## Claude Code: Session Hook

Register `remember-da-hook` as a `UserPromptSubmit` hook to auto-inject project context at the top of every prompt. Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "remember-da-hook"}]
      }
    ]
  }
}
```

The hook detects the current working directory, queries the DB, and prepends a context block to the user's message. It silently no-ops if the project has no content or on any error.

---

## Web UI

Run the dashboard at `http://localhost:5000`:

```bash
remember-da-web
```

Shows: project selector, kanban task board (new / in_progress / blocked / done), map entries with search, commands and notes panels.

---

## MCP Tools Reference

### Project

| Tool | Description |
|---|---|
| `get_session_context(project_path)` | Load active tasks, recent map entries, commands, and notes. Call at session start. Auto-registers the project if unknown. |
| `init_project(path, name)` | Register a project by its absolute path. Idempotent. |
| `init_and_fill_project(path, name)` | Register a project and return a prompt for the agent to populate it by exploring the codebase. |
| `save_session(project_path)` | Return a prompt for the agent to snapshot current session knowledge into the DB. |
| `get_project(project_path)` | Get project metadata. |
| `remove_project(project_path)` | Delete a project and all its data. |

### Tasks

| Tool | Description |
|---|---|
| `list_tasks(project_path, status?)` | List tasks, optionally filtered by status (`new`, `in_progress`, `blocked`, `done`). |
| `add_task(project_path, title, description?)` | Create a task. |
| `update_task(task_id, status?, title?, description?)` | Update task fields. |
| `delete_task(task_id)` | Remove a task. |

### Codebase Map

| Tool | Description |
|---|---|
| `upsert_map_entry(project_path, path, description, tags?, notes?)` | Add or update a file/module entry. |
| `get_map_entry(project_path, path)` | Get a single entry by file path. |
| `list_map_entries(project_path, tag?)` | List all entries, optionally filtered by tag. |
| `search_map(project_path, query)` | Full-text search across path, description, tags, and notes. |
| `delete_map_entry(project_path, path)` | Remove a map entry. |

### Commands

| Tool | Description |
|---|---|
| `get_commands(project_path)` | List all named commands (e.g. build, test, run). |
| `set_command(project_path, name, command, description?)` | Add or update a command. |
| `delete_command(project_path, name)` | Remove a command. |

### Notes

| Tool | Description |
|---|---|
| `list_notes(project_path)` | List all key/value notes. |
| `get_note(project_path, key)` | Get a specific note. |
| `set_note(project_path, key, value)` | Add or update a note. |
| `delete_note(project_path, key)` | Remove a note. |

---

## File Structure

```
remember_da_project/
├── pyproject.toml
├── README.md
├── src/
│   └── remember_da_project/
│       ├── __init__.py
│       ├── db.py          # schema init + all CRUD helpers (SQLite + FTS5)
│       ├── server.py      # FastMCP server + tool definitions
│       ├── web.py         # Flask web UI (localhost:5000)
│       └── hook.py        # Claude Code UserPromptSubmit hook
└── tests/
    └── test_basic.py
```

Database: `~/.local/share/remember_da_project/memory.db`

---

## Requirements

- Python 3.10+
- `fastmcp >= 2.0`
- `flask >= 3.0`
