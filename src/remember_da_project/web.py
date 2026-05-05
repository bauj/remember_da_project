"""Flask web UI for remember_da_project — read/write dashboard at http://localhost:5000."""

from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from . import db

app = Flask(__name__)

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>remember_da_project{% if project %} — {{ project.name }}{% endif %}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: ui-monospace, monospace; background: #0f0f0f; color: #e0e0e0; min-height: 100vh; }
    a { color: #7eb8f7; text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* Layout */
    .sidebar { width: 280px; height: 100vh; background: #1a1a1a; border-right: 1px solid #2a2a2a;
               padding: 1.5rem 1rem; position: fixed; top: 0; left: 0; overflow-y: auto; }
    .main { margin-left: 280px; padding: 2rem; }

    /* Sidebar */
    .sidebar h1 { font-size: 1rem; color: #7eb8f7; margin-bottom: 1.5rem; letter-spacing: 0.05em; }
    .sidebar input[type=text] { width: 100%; background: #111; border: 1px solid #333; color: #e0e0e0;
                                 padding: 0.4rem 0.6rem; border-radius: 4px; font-family: inherit;
                                 font-size: 0.8rem; margin-bottom: 0.4rem; }
    .sidebar button { width: 100%; background: #1e3a5f; color: #7eb8f7; border: 1px solid #2a5a9f;
                       padding: 0.4rem; border-radius: 4px; font-family: inherit; cursor: pointer;
                       font-size: 0.8rem; margin-bottom: 1rem; }
    .sidebar button:hover { background: #2a4f7a; }
    .project-list { list-style: none; }
    .project-list li { padding: 0.35rem 0.5rem; border-radius: 4px; font-size: 0.8rem; cursor: pointer; }
    .project-list li:hover { background: #252525; }
    .project-list li.active { background: #1e3a5f; color: #7eb8f7; }
    .project-list li .path { font-size: 0.65rem; color: #666; display: block; overflow: hidden;
                              text-overflow: ellipsis; white-space: nowrap; }

    /* Sections */
    .section { margin-bottom: 2.5rem; }
    .section-header { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;
                       border-bottom: 1px solid #2a2a2a; padding-bottom: 0.5rem; }
    .section-header h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em; color: #888; }
    .badge { font-size: 0.7rem; background: #2a2a2a; color: #888; padding: 0.15rem 0.4rem; border-radius: 10px; }

    /* Kanban */
    .kanban { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
    .kanban-col { background: #1a1a1a; border-radius: 6px; padding: 0.75rem; }
    .kanban-col h3 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em;
                     margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid #2a2a2a; }
    .col-new h3 { color: #888; }
    .col-in_progress h3 { color: #f0a500; }
    .col-blocked h3 { color: #e05555; }
    .col-done h3 { color: #4caf50; }
    .task-card { background: #242424; border-radius: 4px; padding: 0.6rem 0.75rem;
                 margin-bottom: 0.5rem; border-left: 3px solid #333; }
    .col-in_progress .task-card { border-left-color: #f0a500; }
    .col-blocked .task-card { border-left-color: #e05555; }
    .col-done .task-card { border-left-color: #4caf50; }
    .task-id { font-size: 0.65rem; color: #555; }
    .task-title { font-size: 0.8rem; margin: 0.2rem 0; }
    .task-desc { font-size: 0.72rem; color: #777; margin-top: 0.2rem; line-height: 1.4; }
    .task-actions { margin-top: 0.5rem; display: flex; gap: 0.4rem; flex-wrap: wrap; }
    .task-actions form { display: inline; }
    .btn-sm { font-size: 0.65rem; padding: 0.15rem 0.4rem; border-radius: 3px; border: 1px solid #333;
               background: #2a2a2a; color: #aaa; cursor: pointer; font-family: inherit; }
    .btn-sm:hover { background: #333; color: #e0e0e0; }
    .btn-danger { border-color: #5a2a2a; color: #e05555; }
    .btn-danger:hover { background: #3a1a1a; }

    /* Add task form */
    .add-form { background: #1a1a1a; border-radius: 6px; padding: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .add-form input, .add-form textarea { background: #111; border: 1px solid #333; color: #e0e0e0;
                                           padding: 0.4rem 0.6rem; border-radius: 4px; font-family: inherit;
                                           font-size: 0.8rem; }
    .add-form input[name=title] { flex: 1; min-width: 200px; }
    .add-form textarea { flex: 2; min-width: 200px; resize: vertical; min-height: 2.5rem; }
    .add-form button { background: #1e3a5f; color: #7eb8f7; border: 1px solid #2a5a9f;
                        padding: 0.4rem 0.8rem; border-radius: 4px; font-family: inherit; cursor: pointer; font-size: 0.8rem; }
    .add-form button:hover { background: #2a4f7a; }

    /* Map entries */
    .search-bar { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
    .search-bar input { flex: 1; background: #111; border: 1px solid #333; color: #e0e0e0;
                         padding: 0.4rem 0.6rem; border-radius: 4px; font-family: inherit; font-size: 0.8rem; }
    .search-bar button { background: #1e3a5f; color: #7eb8f7; border: 1px solid #2a5a9f;
                          padding: 0.4rem 0.8rem; border-radius: 4px; font-family: inherit; cursor: pointer; font-size: 0.8rem; }
    .map-entry { background: #1a1a1a; border-radius: 4px; padding: 0.6rem 0.75rem;
                 margin-bottom: 0.5rem; border-left: 3px solid #2a5a9f; }
    .map-path { font-size: 0.8rem; color: #7eb8f7; font-weight: bold; }
    .map-tags { font-size: 0.68rem; color: #666; margin-top: 0.15rem; }
    .map-desc { font-size: 0.78rem; margin-top: 0.25rem; line-height: 1.4; }
    .map-notes { font-size: 0.72rem; color: #888; margin-top: 0.2rem; font-style: italic; }

    /* Commands & Notes */
    .kv-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
    .kv-table td { padding: 0.4rem 0.6rem; border-bottom: 1px solid #1e1e1e; }
    .kv-table tr:last-child td { border-bottom: none; }
    .kv-table .key { color: #7eb8f7; width: 140px; }
    .kv-table .val { color: #e0e0e0; font-family: ui-monospace, monospace; }
    .kv-table .desc { color: #666; font-size: 0.72rem; }

    /* Empty state */
    .empty { color: #444; font-size: 0.8rem; padding: 0.5rem 0; }

    /* No project */
    .welcome { max-width: 480px; margin: 4rem auto; text-align: center; color: #555; }
    .welcome h2 { color: #7eb8f7; margin-bottom: 1rem; font-size: 1.1rem; }
    .welcome p { font-size: 0.85rem; line-height: 1.6; }
  </style>
</head>
<body>

<!-- Sidebar -->
<div class="sidebar">
  <h1>remember_da_project</h1>

  <form method="GET" action="{{ url_for('index') }}">
    <input type="text" name="path" placeholder="Project path…" value="{{ selected_path or '' }}">
    <button type="submit">Load</button>
  </form>

  {% if projects %}
  <ul class="project-list">
    {% for p in projects %}
    <li class="{{ 'active' if p.path == selected_path else '' }}">
      <a href="{{ url_for('index', path=p.path) }}" style="color: inherit; text-decoration: none;">
        {{ p.name }}
        <span class="path">{{ p.path }}</span>
      </a>
    </li>
    {% endfor %}
  </ul>
  {% endif %}
</div>

<!-- Main content -->
<div class="main">
  {% if not project %}
  <div class="welcome">
    <h2>No project selected</h2>
    <p>Enter an absolute project path in the sidebar, or use the MCP tools to init a project first.</p>
  </div>
  {% else %}

  <!-- Tasks -->
  <div class="section">
    <div class="section-header">
      <h2>Tasks</h2>
      <span class="badge">{{ tasks|length }}</span>
    </div>

    <div class="kanban">
      {% for col_status in ['new', 'in_progress', 'blocked', 'done'] %}
      <div class="kanban-col col-{{ col_status }}">
        <h3>{{ col_status.replace('_', ' ') }}</h3>
        {% for task in tasks if task.status == col_status %}
        <div class="task-card">
          <div class="task-id">#{{ task.id }}</div>
          <div class="task-title">{{ task.title }}</div>
          {% if task.description %}<div class="task-desc">{{ task.description }}</div>{% endif %}
          <div class="task-actions">
            {% for s in ['new', 'in_progress', 'blocked', 'done'] if s != task.status %}
            <form method="POST" action="{{ url_for('task_update', task_id=task.id) }}">
              <input type="hidden" name="status" value="{{ s }}">
              <input type="hidden" name="redirect_path" value="{{ selected_path }}">
              <button type="submit" class="btn-sm">→ {{ s.replace('_',' ') }}</button>
            </form>
            {% endfor %}
            <form method="POST" action="{{ url_for('task_delete', task_id=task.id) }}">
              <input type="hidden" name="redirect_path" value="{{ selected_path }}">
              <button type="submit" class="btn-sm btn-danger">delete</button>
            </form>
          </div>
        </div>
        {% else %}
        {% if loop.first %}<div class="empty">empty</div>{% endif %}
        {% endfor %}
      </div>
      {% endfor %}
    </div>

    <!-- Add task -->
    <form class="add-form" method="POST" action="{{ url_for('task_add') }}" style="margin-top: 1rem;">
      <input type="hidden" name="project_path" value="{{ selected_path }}">
      <input type="text" name="title" placeholder="New task title…" required>
      <textarea name="description" placeholder="Description (optional)…"></textarea>
      <button type="submit">Add task</button>
    </form>
  </div>

  <!-- Commands -->
  <div class="section">
    <div class="section-header">
      <h2>Commands</h2>
      <span class="badge">{{ commands|length }}</span>
    </div>
    {% if commands %}
    <table class="kv-table">
      {% for cmd in commands %}
      <tr>
        <td class="key">{{ cmd.name }}</td>
        <td class="val">{{ cmd.command }}</td>
        <td class="desc">{{ cmd.description or '' }}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <div class="empty">No commands stored. Use set_command via MCP.</div>
    {% endif %}
  </div>

  <!-- Notes -->
  <div class="section">
    <div class="section-header">
      <h2>Notes</h2>
      <span class="badge">{{ notes|length }}</span>
    </div>
    {% if notes %}
    <table class="kv-table">
      {% for note in notes %}
      <tr>
        <td class="key">{{ note.key }}</td>
        <td class="val">{{ note.value }}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <div class="empty">No notes stored. Use set_note via MCP.</div>
    {% endif %}
  </div>

  <!-- Codebase Map -->
  <div class="section">
    <div class="section-header">
      <h2>Codebase Map</h2>
      <span class="badge">{{ map_entries|length }}</span>
    </div>

    <form class="search-bar" method="GET" action="{{ url_for('index') }}">
      <input type="hidden" name="path" value="{{ selected_path }}">
      <input type="text" name="q" placeholder="Search map…" value="{{ search_query or '' }}">
      <button type="submit">Search</button>
    </form>

    {% if map_entries %}
      {% for entry in map_entries %}
      <div class="map-entry">
        <div class="map-path">{{ entry.path }}</div>
        {% if entry.tags %}<div class="map-tags">{{ entry.tags }}</div>{% endif %}
        <div class="map-desc">{{ entry.description }}</div>
        {% if entry.notes %}<div class="map-notes">{{ entry.notes }}</div>{% endif %}
      </div>
      {% endfor %}
    {% else %}
    <div class="empty">No map entries{% if search_query %} matching "{{ search_query }}"{% endif %}. Use upsert_map_entry via MCP.</div>
    {% endif %}
  </div>

  {% endif %}
</div>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    selected_path = request.args.get("path", "").strip() or None
    search_query = request.args.get("q", "").strip() or None

    # Load all known projects for the sidebar
    import sqlite3
    from . import db as _db
    projects = []
    try:
        with _db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
            projects = [dict(r) for r in rows]
    except Exception:
        pass

    project = None
    tasks = []
    commands = []
    notes = []
    map_entries = []

    if selected_path:
        project = db.get_project(selected_path)
        if project:
            tasks = db.list_tasks(selected_path)
            commands = db.get_commands(selected_path)
            notes = db.list_notes(selected_path)
            if search_query:
                map_entries = db.search_map(selected_path, search_query)
            else:
                map_entries = db.list_map_entries(selected_path)

    return render_template_string(
        TEMPLATE,
        project=project,
        projects=projects,
        selected_path=selected_path,
        tasks=tasks,
        commands=commands,
        notes=notes,
        map_entries=map_entries,
        search_query=search_query,
    )


@app.route("/tasks/add", methods=["POST"])
def task_add():
    project_path = request.form["project_path"]
    title = request.form["title"].strip()
    description = request.form.get("description", "").strip() or None
    if title:
        db.add_task(project_path, title, description)
    return redirect(url_for("index", path=project_path))


@app.route("/tasks/<int:task_id>/update", methods=["POST"])
def task_update(task_id: int):
    status = request.form.get("status")
    title = request.form.get("title")
    description = request.form.get("description")
    redirect_path = request.form.get("redirect_path", "")
    db.update_task(task_id, status=status or None, title=title or None, description=description or None)
    return redirect(url_for("index", path=redirect_path))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
def task_delete(task_id: int):
    redirect_path = request.form.get("redirect_path", "")
    db.delete_task(task_id)
    return redirect(url_for("index", path=redirect_path))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
