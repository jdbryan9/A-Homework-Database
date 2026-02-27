from __future__ import annotations

import html
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "homework.db"
HOST = "0.0.0.0"
PORT = 8000


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            course TEXT NOT NULL,
            due_date TEXT NOT NULL,
            notes TEXT DEFAULT ''
        )
        """
    )
    assignment_count = db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0]

    if assignment_count == 0:
        today = date.today()
        sample_assignments = [
            ("Read Chapter 5", "English", (today + timedelta(days=2)).isoformat(), "Summarize key themes."),
            ("Problem Set 7", "Calculus", (today + timedelta(days=5)).isoformat(), "Focus on integrals."),
            ("Lab Report", "Biology", (today + timedelta(days=1)).isoformat(), "Include microscope observations."),
            ("World War II Timeline", "History", (today + timedelta(days=8)).isoformat(), "Add at least 10 major events."),
        ]
        db.executemany(
            "INSERT INTO assignments (title, course, due_date, notes) VALUES (?, ?, ?, ?)",
            sample_assignments,
        )

    db.commit()
    db.close()


def assignment_status(due_date_text: str) -> tuple[bool, bool]:
    due = datetime.strptime(due_date_text, "%Y-%m-%d").date()
    days_left = (due - date.today()).days
    return (0 <= days_left <= 3, days_left < 0)


def render_page() -> str:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    assignments = db.execute(
        "SELECT id, title, course, due_date, notes FROM assignments ORDER BY due_date ASC"
    ).fetchall()
    db.close()

    rows = []
    for a in assignments:
        is_due_soon, is_overdue = assignment_status(a["due_date"])
        row_class = "overdue" if is_overdue else "due-soon" if is_due_soon else ""
        warning_icon = " <span title='Due within 3 days'>⚠️</span>" if is_due_soon else ""
        notes = html.escape(a["notes"]) if a["notes"] else "—"
        rows.append(
            f"""
            <tr class='{row_class}'>
                <td><strong>{html.escape(a['title'])}</strong>{warning_icon}</td>
                <td>{html.escape(a['course'])}</td>
                <td>{html.escape(a['due_date'])}</td>
                <td class='muted'>{notes}</td>
                <td>
                    <form method='post' action='/delete'>
                        <input type='hidden' name='id' value='{a['id']}' />
                        <button class='danger'>Delete</button>
                    </form>
                </td>
            </tr>
            """
        )

    table_body = "\n".join(rows) if rows else "<tr><td colspan='5' class='muted'>No assignments yet.</td></tr>"

    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Homework Tracker</title>
<style>
:root {{ color-scheme: light; }}
body {{ font-family: Inter, system-ui, sans-serif; margin: 0; background: linear-gradient(120deg,#f8f8ff,#edf6ff); color:#243041; }}
.container {{ max-width: 1100px; margin: 30px auto; padding: 0 16px; }}
h1 {{ margin-bottom: 6px; }}
.subtitle {{ color: #607086; margin-top: 0; }}
.grid {{ display: grid; gap: 18px; grid-template-columns: 320px 1fr; align-items: start; }}
.card {{ background: white; border-radius: 14px; padding: 18px; box-shadow: 0 10px 24px rgba(42,57,88,.08); }}
label {{ display:block; font-size: .9rem; margin-bottom: 6px; font-weight:600; }}
input, textarea {{ width: 100%; padding: 10px; border:1px solid #cdd8e6; border-radius: 8px; box-sizing: border-box; margin-bottom: 12px; }}
button {{ background:#2962ff; color:white; border:none; border-radius:8px; padding:10px 14px; cursor:pointer; font-weight:600; }}
button:hover {{ filter: brightness(.96); }}
.danger {{ background:#fff; color:#ba2d2d; border:1px solid #eab4b4; padding:6px 10px; }}
table {{ width:100%; border-collapse: collapse; }}
th, td {{ text-align:left; padding: 10px; border-bottom:1px solid #eef1f5; font-size:.95rem; }}
th {{ font-size:.86rem; text-transform:uppercase; letter-spacing:.03em; color:#5d6f85; }}
.badge {{ background:#fff4ce; color:#7a5900; border:1px solid #ffe08b; border-radius: 999px; padding: 4px 10px; font-size:.8rem; }}
.due-soon {{ background:#fffaf0; }}
.overdue {{ background:#fff1f1; }}
.muted {{ color:#6b7a90; }}
@media (max-width:900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class='container'>
  <h1>📚 Student Homework Tracker</h1>
  <p class='subtitle'>Track assignments, due dates, and notes in a simple relational database.</p>
  <div class='grid'>
    <section class='card'>
      <h2>Add Assignment</h2>
      <form method='post' action='/add'>
        <label>Title</label>
        <input name='title' required>
        <label>Course</label>
        <input name='course' required>
        <label>Due Date</label>
        <input type='date' name='due_date' min='{date.today().isoformat()}' required>
        <label>Notes</label>
        <textarea name='notes' rows='3' placeholder='Optional notes'></textarea>
        <button>Add Assignment</button>
      </form>
    </section>
    <section class='card'>
      <div style='display:flex;justify-content:space-between;align-items:center;gap:10px;'>
        <h2 style='margin:0;'>Assignments</h2>
        <span class='badge'>⚠️ due within 3 days</span>
      </div>
      <table>
        <thead><tr><th>Title</th><th>Course</th><th>Due Date</th><th>Notes</th><th></th></tr></thead>
        <tbody>{table_body}</tbody>
      </table>
    </section>
  </div>
</div>
</body>
</html>
"""


class HomeworkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            page = render_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return

        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(content_length).decode("utf-8")
        fields = parse_qs(data)

        if parsed.path == "/add":
            title = fields.get("title", [""])[0].strip()
            course = fields.get("course", [""])[0].strip()
            due_date = fields.get("due_date", [""])[0].strip()
            notes = fields.get("notes", [""])[0].strip()
            if title and course and due_date:
                db = sqlite3.connect(DB_PATH)
                db.execute(
                    "INSERT INTO assignments (title, course, due_date, notes) VALUES (?, ?, ?, ?)",
                    (title, course, due_date, notes),
                )
                db.commit()
                db.close()
            return self.redirect_home()

        if parsed.path == "/delete":
            assignment_id = fields.get("id", [""])[0].strip()
            if assignment_id.isdigit():
                db = sqlite3.connect(DB_PATH)
                db.execute("DELETE FROM assignments WHERE id = ?", (int(assignment_id),))
                db.commit()
                db.close()
            return self.redirect_home()

        self.send_error(404)

    def redirect_home(self) -> None:
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def run() -> None:
    init_db()
    server = HTTPServer((HOST, PORT), HomeworkHandler)
    print(f"Homework tracker running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
