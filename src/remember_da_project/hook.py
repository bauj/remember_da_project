"""
Claude Code session hook for remember_da_project.

Reads session context from the DB and outputs a formatted block that Claude Code
prepends to the user's first message via the UserPromptSubmit hook.

Register in .claude/settings.json:
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
"""

import json
import os
import sys
from pathlib import Path

from . import db


def format_context(ctx: dict) -> str:
    """Format session context as a compact text block for injection."""
    lines = []
    project = ctx["project"]
    lines.append(f"=== remember_da_project: {project['name']} ===")
    lines.append(f"Path: {project['path']}")

    # Commands
    if ctx["commands"]:
        lines.append("\n-- Commands --")
        for cmd in ctx["commands"]:
            desc = f"  # {cmd['description']}" if cmd["description"] else ""
            lines.append(f"  {cmd['name']}: {cmd['command']}{desc}")

    # Active tasks
    if ctx["active_tasks"]:
        lines.append("\n-- Active Tasks --")
        for task in ctx["active_tasks"]:
            desc = f": {task['description']}" if task["description"] else ""
            lines.append(f"  [{task['status']}] #{task['id']} {task['title']}{desc}")

    # Notes
    if ctx["notes"]:
        lines.append("\n-- Notes --")
        for note in ctx["notes"]:
            lines.append(f"  {note['key']}: {note['value']}")

    # Recent map entries
    if ctx["recent_map_entries"]:
        lines.append("\n-- Recent Codebase Map (last 20) --")
        for entry in ctx["recent_map_entries"]:
            tags = f" [{entry['tags']}]" if entry["tags"] else ""
            notes = f"\n    note: {entry['notes']}" if entry["notes"] else ""
            lines.append(f"  {entry['path']}{tags}\n    {entry['description']}{notes}")

    lines.append("=== end of session context ===")
    return "\n".join(lines)


def main() -> None:
    """
    Hook entry point. Reads the UserPromptSubmit hook input from stdin (JSON),
    injects project context, and writes the modified payload to stdout.

    Claude Code hook protocol:
    - stdin:  JSON with at least {"prompt": "..."}
    - stdout: JSON with {"prompt": "..."} — the modified prompt
    - If no project is known for cwd, pass through unchanged.
    """
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        # If we can't parse input, pass through
        sys.stdout.write(raw if raw else "")
        return

    cwd = os.getcwd()

    try:
        ctx = db.get_session_context(cwd)
        # Only inject if project has any content worth showing
        has_content = (
            ctx["active_tasks"]
            or ctx["commands"]
            or ctx["notes"]
            or ctx["recent_map_entries"]
        )
        if has_content:
            context_block = format_context(ctx)
            original_prompt = payload.get("prompt", "")
            payload["prompt"] = f"{context_block}\n\n{original_prompt}"
    except Exception:
        # Never crash the hook — silently pass through on any error
        pass

    sys.stdout.write(json.dumps(payload))


if __name__ == "__main__":
    main()
