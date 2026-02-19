import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "tasks.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            parent_id INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (parent_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    """)
    db.commit()
    db.close()


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "completed": bool(row["completed"]),
        "completed_at": row["completed_at"],
        "parent_id": row["parent_id"],
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
    }


def build_tree(tasks, parent_id=None):
    """Build nested task tree from flat list."""
    nodes = []
    for t in tasks:
        if t["parent_id"] == parent_id:
            node = dict(t)
            node["children"] = build_tree(tasks, t["id"])
            nodes.append(node)
    nodes.sort(key=lambda n: n["sort_order"])
    return nodes


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/tasks")
def list_tasks():
    db = get_db()
    rows = db.execute("SELECT * FROM tasks ORDER BY sort_order").fetchall()
    tasks = [task_to_dict(r) for r in rows]

    # Build lookup for ancestor checks
    by_id = {t["id"]: t for t in tasks}

    def all_ancestors_completed(task):
        """Return True if every ancestor of this task is also completed."""
        pid = task["parent_id"]
        while pid is not None:
            parent = by_id.get(pid)
            if not parent or not parent["completed"]:
                return False
            pid = parent["parent_id"]
        return True

    # A task belongs in Completed only if it AND all ancestors are completed.
    # Otherwise it stays in Current (even if individually checked).
    current = [t for t in tasks if not t["completed"] or not all_ancestors_completed(t)]
    completed = [t for t in tasks if t["completed"] and all_ancestors_completed(t)]

    return jsonify({
        "current": build_tree(current),
        "completed": build_tree(completed),
    })


@app.route("/api/tasks", methods=["POST"])
def create_task():
    db = get_db()
    data = request.json
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title required"}), 400

    parent_id = data.get("parent_id")

    # Get next sort_order
    row = db.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM tasks").fetchone()
    sort_order = row["next_order"]

    cursor = db.execute(
        "INSERT INTO tasks (title, parent_id, sort_order) VALUES (?, ?, ?)",
        (title, parent_id, sort_order),
    )
    db.commit()

    task = task_to_dict(
        db.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    )
    return jsonify(task), 201


def complete_subtasks(db, task_id, completed_at):
    """Recursively mark all subtasks as completed."""
    children = db.execute("SELECT id FROM tasks WHERE parent_id = ? AND completed = 0", (task_id,)).fetchall()
    for child in children:
        db.execute(
            "UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?",
            (completed_at, child["id"]),
        )
        complete_subtasks(db, child["id"], completed_at)


def uncomplete_subtasks(db, task_id):
    """Recursively mark all subtasks as not completed."""
    children = db.execute("SELECT id FROM tasks WHERE parent_id = ? AND completed = 1", (task_id,)).fetchall()
    for child in children:
        db.execute(
            "UPDATE tasks SET completed = 0, completed_at = NULL WHERE id = ?",
            (child["id"],),
        )
        uncomplete_subtasks(db, child["id"])


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
    db = get_db()
    data = request.json

    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return jsonify({"error": "Not found"}), 404

    if "completed" in data:
        completed = bool(data["completed"])
        completed_at = datetime.utcnow().isoformat() if completed else None
        db.execute(
            "UPDATE tasks SET completed = ?, completed_at = ? WHERE id = ?",
            (int(completed), completed_at, task_id),
        )
        if completed:
            complete_subtasks(db, task_id, completed_at)
        else:
            uncomplete_subtasks(db, task_id)

    if "title" in data:
        db.execute("UPDATE tasks SET title = ? WHERE id = ?", (data["title"], task_id))

    if "parent_id" in data:
        new_parent = data["parent_id"]
        db.execute("UPDATE tasks SET parent_id = ? WHERE id = ?", (new_parent, task_id))

    if "sort_order" in data:
        db.execute("UPDATE tasks SET sort_order = ? WHERE id = ?", (data["sort_order"], task_id))

    db.commit()

    updated = task_to_dict(
        db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    )
    return jsonify(updated)


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return "", 204


@app.route("/api/tasks/reorder", methods=["POST"])
def reorder_tasks():
    """Bulk update parent_id and sort_order for drag-and-drop."""
    db = get_db()
    items = request.json.get("items", [])
    for item in items:
        db.execute(
            "UPDATE tasks SET parent_id = ?, sort_order = ? WHERE id = ?",
            (item.get("parent_id"), item["sort_order"], item["id"]),
        )
    db.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5002)
