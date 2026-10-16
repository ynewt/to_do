# To-Do

A to-do list with nested subtasks and drag-and-drop ordering. It's a Flask app with a small JSON API, and it stores tasks in a local SQLite database (`tasks.db`).

## Features

- **Add tasks** by typing in the box and pressing Enter.
- **Nested subtasks:** drag a task onto the middle of another task to make it a subtask. Drag onto the top or bottom edge to reorder it above or below instead. Subtasks can be nested several levels deep.
- **Inline editing:** click a task's title to rename it (Enter saves, Escape cancels).
- **Completing tasks:** checking off a task also checks off all its subtasks, and unchecking it unchecks them.
- **Completed section:** a task moves to *Completed* only once it and all its parent tasks are done. Completed tasks are grouped by the date they were finished.
- **Delete** a task, which also deletes its subtasks.

## Running it

Requires Python 3 and Flask.

```bash
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5002. The database file `tasks.db` is created automatically on first run.

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/tasks` | All tasks, split into `current` and `completed` trees |
| `POST` | `/api/tasks` | Create a task (`title`, optional `parent_id`) |
| `PATCH` | `/api/tasks/<id>` | Update `title`, `completed`, `parent_id` or `sort_order` |
| `DELETE` | `/api/tasks/<id>` | Delete a task and its subtasks |
| `POST` | `/api/tasks/reorder` | Bulk-update `parent_id` and `sort_order` after a drag and drop |

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask app and API on port 5002 |
| `templates/index.html` | The UI: HTML, CSS and JavaScript |
| `tasks.db` | SQLite database holding the tasks |
| `requirements.txt` | Python dependencies (`flask`) |
