"""Basic smoke tests for remember_da_project."""

import os
import tempfile
import pytest

# Point the DB at a temp file for tests
import remember_da_project.db as db_module

@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Redirect DB to a temp directory for each test."""
    monkeypatch.setattr(db_module, "DB_DIR", tmp_path)
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    db_module.init_db()
    yield


PROJECT_PATH = "/tmp/test_project"


def test_init_and_get_project():
    p = db_module.init_project(PROJECT_PATH, "Test Project")
    assert p["path"] == PROJECT_PATH
    assert p["name"] == "Test Project"

    got = db_module.get_project(PROJECT_PATH)
    assert got is not None
    assert got["id"] == p["id"]


def test_init_project_idempotent():
    p1 = db_module.init_project(PROJECT_PATH, "Test")
    p2 = db_module.init_project(PROJECT_PATH, "Test Again")
    assert p1["id"] == p2["id"]


def test_remove_project():
    db_module.init_project(PROJECT_PATH, "Test")
    removed = db_module.remove_project(PROJECT_PATH)
    assert removed is True
    assert db_module.get_project(PROJECT_PATH) is None


def test_remove_project_not_found():
    removed = db_module.remove_project("/nonexistent")
    assert removed is False


def test_tasks_crud():
    db_module.init_project(PROJECT_PATH, "Test")

    task = db_module.add_task(PROJECT_PATH, "Fix the bug", "It crashes on startup")
    assert task["title"] == "Fix the bug"
    assert task["status"] == "new"

    tasks = db_module.list_tasks(PROJECT_PATH)
    assert len(tasks) == 1

    updated = db_module.update_task(task["id"], status="in_progress")
    assert updated["status"] == "in_progress"

    tasks_in_progress = db_module.list_tasks(PROJECT_PATH, status="in_progress")
    assert len(tasks_in_progress) == 1

    deleted = db_module.delete_task(task["id"])
    assert deleted is True
    assert db_module.list_tasks(PROJECT_PATH) == []


def test_task_invalid_status():
    db_module.init_project(PROJECT_PATH, "Test")
    task = db_module.add_task(PROJECT_PATH, "A task")
    with pytest.raises(ValueError):
        db_module.update_task(task["id"], status="flying")


def test_map_entry_crud():
    db_module.init_project(PROJECT_PATH, "Test")

    entry = db_module.upsert_map_entry(
        PROJECT_PATH,
        "src/auth/jwt.py",
        "Handles JWT token creation and validation",
        tags="auth,jwt,security",
        notes="Uses HS256 algorithm",
    )
    assert entry["path"] == "src/auth/jwt.py"

    got = db_module.get_map_entry(PROJECT_PATH, "src/auth/jwt.py")
    assert got is not None
    assert got["description"] == "Handles JWT token creation and validation"

    # Upsert update
    updated = db_module.upsert_map_entry(PROJECT_PATH, "src/auth/jwt.py", "Updated desc")
    assert updated["description"] == "Updated desc"

    entries = db_module.list_map_entries(PROJECT_PATH)
    assert len(entries) == 1

    deleted = db_module.delete_map_entry(PROJECT_PATH, "src/auth/jwt.py")
    assert deleted is True
    assert db_module.get_map_entry(PROJECT_PATH, "src/auth/jwt.py") is None


def test_map_search():
    db_module.init_project(PROJECT_PATH, "Test")
    db_module.upsert_map_entry(PROJECT_PATH, "src/auth/jwt.py", "JWT token validation", tags="auth")
    db_module.upsert_map_entry(PROJECT_PATH, "src/api/routes.py", "API route definitions", tags="api")

    results = db_module.search_map(PROJECT_PATH, "JWT")
    assert len(results) == 1
    assert results[0]["path"] == "src/auth/jwt.py"

    results_api = db_module.search_map(PROJECT_PATH, "API")
    assert len(results_api) == 1


def test_map_list_by_tag():
    db_module.init_project(PROJECT_PATH, "Test")
    db_module.upsert_map_entry(PROJECT_PATH, "src/auth/jwt.py", "JWT", tags="auth,security")
    db_module.upsert_map_entry(PROJECT_PATH, "src/api/routes.py", "Routes", tags="api")

    auth_entries = db_module.list_map_entries(PROJECT_PATH, tag="auth")
    assert len(auth_entries) == 1
    assert auth_entries[0]["path"] == "src/auth/jwt.py"


def test_commands_crud():
    db_module.init_project(PROJECT_PATH, "Test")

    cmd = db_module.set_command(PROJECT_PATH, "build", "make dev", "Build the project")
    assert cmd["name"] == "build"
    assert cmd["command"] == "make dev"

    # Upsert
    cmd2 = db_module.set_command(PROJECT_PATH, "build", "make prod")
    assert cmd2["command"] == "make prod"

    cmds = db_module.get_commands(PROJECT_PATH)
    assert len(cmds) == 1

    deleted = db_module.delete_command(PROJECT_PATH, "build")
    assert deleted is True
    assert db_module.get_commands(PROJECT_PATH) == []


def test_notes_crud():
    db_module.init_project(PROJECT_PATH, "Test")

    note = db_module.set_note(PROJECT_PATH, "orm", "SQLAlchemy 2.x")
    assert note["key"] == "orm"
    assert note["value"] == "SQLAlchemy 2.x"

    got = db_module.get_note(PROJECT_PATH, "orm")
    assert got is not None

    notes = db_module.list_notes(PROJECT_PATH)
    assert len(notes) == 1

    deleted = db_module.delete_note(PROJECT_PATH, "orm")
    assert deleted is True
    assert db_module.get_note(PROJECT_PATH, "orm") is None


def test_cascade_delete():
    """Removing a project deletes all its tasks, map entries, commands, notes."""
    db_module.init_project(PROJECT_PATH, "Test")
    db_module.add_task(PROJECT_PATH, "A task")
    db_module.upsert_map_entry(PROJECT_PATH, "src/foo.py", "Foo module")
    db_module.set_command(PROJECT_PATH, "test", "pytest")
    db_module.set_note(PROJECT_PATH, "key", "value")

    db_module.remove_project(PROJECT_PATH)

    # Re-init to check tables are empty for this project
    db_module.init_project(PROJECT_PATH, "Test")
    assert db_module.list_tasks(PROJECT_PATH) == []
    assert db_module.list_map_entries(PROJECT_PATH) == []
    assert db_module.get_commands(PROJECT_PATH) == []
    assert db_module.list_notes(PROJECT_PATH) == []


def test_get_session_context():
    ctx = db_module.get_session_context(PROJECT_PATH)
    assert "project" in ctx
    assert ctx["project"]["path"] == PROJECT_PATH
    assert "active_tasks" in ctx
    assert "commands" in ctx
    assert "notes" in ctx
    assert "recent_map_entries" in ctx

    # Add some content
    db_module.add_task(PROJECT_PATH, "Task 1")
    db_module.set_command(PROJECT_PATH, "run", "python main.py")
    db_module.upsert_map_entry(PROJECT_PATH, "main.py", "Entry point")

    ctx2 = db_module.get_session_context(PROJECT_PATH)
    assert len(ctx2["active_tasks"]) == 1
    assert len(ctx2["commands"]) == 1
    assert len(ctx2["recent_map_entries"]) == 1
