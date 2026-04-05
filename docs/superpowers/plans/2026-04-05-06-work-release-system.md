# Phase 6: Work Release System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Work Release web UI and HTTP server that lets users review, approve, reject, and auto-release agent work before execution. This is the human-in-the-loop approval gate that sits between agent output and action execution.

**Architecture:** A lightweight Python HTTP server (`release-server.py`) serves a single-page dashboard and exposes a JSON REST API. The dashboard polls the API every 5 seconds to show pending releases, lets users approve/reject/auto-release work items, and manage auto-release rules. All state lives in SQLite (`work_releases` and `auto_release_rules` tables, already defined in db-init.py). Three new db-utils.py commands provide CLI access to the same data for agents.

**Tech Stack:** Python 3 (http.server, sqlite3, json), HTML5, CSS3, vanilla JavaScript

---

## File Map

| File | Responsibility |
|------|---------------|
| `scripts/release-server.py` | HTTP server on port 53800 — serves UI and REST API |
| `ui/index.html` | Single-page dashboard — releases table, rules panel, status bar |
| `ui/style.css` | Professional dark theme with status badges and responsive layout |
| `ui/app.js` | Vanilla JS — fetch/render releases, click handlers, auto-refresh, batch ops |
| `scripts/db-utils.py` | Add commands: create-release, list-releases, update-release (18 -> 21 total) |

---

### Task 1: Add Work Release Commands to db-utils.py

**Files:**
- Modify: `scripts/db-utils.py`

- [ ] **Step 1: Add `cmd_create_release` function**

Add this function before the `COMMANDS` dict:

```python
def cmd_create_release(args):
    task_id = agent_id = title = action_type = None
    agent_level = 1
    description = input_preview = output_preview = None
    i = 0
    while i < len(args):
        if args[i] == "--task-id":
            task_id = args[i + 1]; i += 2
        elif args[i] == "--agent-id":
            agent_id = args[i + 1]; i += 2
        elif args[i] == "--title":
            title = args[i + 1]; i += 2
        elif args[i] == "--action-type":
            action_type = args[i + 1]; i += 2
        elif args[i] == "--agent-level":
            agent_level = int(args[i + 1]); i += 2
        elif args[i] == "--description":
            description = args[i + 1]; i += 2
        elif args[i] == "--input-preview":
            input_preview = args[i + 1]; i += 2
        elif args[i] == "--output-preview":
            output_preview = args[i + 1]; i += 2
        else:
            i += 1

    if not task_id or not agent_id or not title or not action_type:
        print("Error: --task-id, --agent-id, --title, and --action-type are required", file=sys.stderr)
        sys.exit(1)

    release_id = str(uuid.uuid4())
    ts = now_iso()

    # Check auto-release rules
    conn = get_conn()
    rules = conn.execute("""
        SELECT rule_id FROM auto_release_rules
        WHERE is_enabled = 1
          AND (match_agent_type = '*' OR match_agent_type = (SELECT agent_type FROM agents WHERE agent_id = ?))
          AND (match_action_type = '*' OR match_action_type = ?)
          AND (match_title_pattern IS NULL OR ? LIKE '%' || match_title_pattern || '%')
    """, (agent_id, action_type, title)).fetchone()

    status = "pending"
    auto_release = 0
    rule_id = None
    if rules:
        status = "auto_released"
        auto_release = 1
        rule_id = rules["rule_id"]
        conn.execute("UPDATE auto_release_rules SET fire_count = fire_count + 1 WHERE rule_id = ?", (rule_id,))

    conn.execute("""
        INSERT INTO work_releases (release_id, task_id, agent_id, agent_level, title, description, action_type, input_preview, output_preview, status, auto_release, auto_release_rule_id, reviewed_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (release_id, task_id, agent_id, agent_level, title, description, action_type, input_preview, output_preview, status, auto_release, rule_id, ts if auto_release else None, ts))

    if status == "auto_released":
        conn.execute("UPDATE tasks SET status = 'in_progress', updated_at = ? WHERE task_id = ? AND status = 'awaiting_release'", (ts, task_id))

    conn.commit()
    conn.close()
    print(json.dumps({"release_id": release_id, "status": status, "auto_released": bool(auto_release)}))
```

- [ ] **Step 2: Add `cmd_list_releases` function**

```python
def cmd_list_releases(args):
    conditions = []
    params = []
    i = 0
    while i < len(args):
        if args[i] == "--status":
            conditions.append("wr.status = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--agent":
            conditions.append("wr.agent_id = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--level":
            conditions.append("wr.agent_level = ?")
            params.append(int(args[i + 1]))
            i += 2
        elif args[i] == "--action-type":
            conditions.append("wr.action_type = ?")
            params.append(args[i + 1])
            i += 2
        else:
            i += 1

    sql = """SELECT wr.*, a.agent_name, a.agent_type
             FROM work_releases wr
             LEFT JOIN agents a ON wr.agent_id = a.agent_id"""
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY wr.created_at DESC"

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))
```

- [ ] **Step 3: Add `cmd_update_release` function**

```python
def cmd_update_release(args):
    release_id = args[0]
    status = None
    i = 1
    while i < len(args):
        if args[i] == "--status":
            status = args[i + 1]; i += 2
        else:
            i += 1

    if not status or status not in ("approved", "rejected"):
        print("Error: --status must be 'approved' or 'rejected'", file=sys.stderr)
        sys.exit(1)

    ts = now_iso()
    conn = get_conn()

    release = conn.execute("SELECT task_id FROM work_releases WHERE release_id = ?", (release_id,)).fetchone()
    if not release:
        print("Error: release not found", file=sys.stderr)
        conn.close()
        sys.exit(1)

    conn.execute("UPDATE work_releases SET status = ?, reviewed_at = ? WHERE release_id = ?", (status, ts, release_id))

    if status == "approved":
        conn.execute("UPDATE tasks SET status = 'in_progress', updated_at = ? WHERE task_id = ? AND status = 'awaiting_release'", (ts, release["task_id"]))
    elif status == "rejected":
        conn.execute("UPDATE tasks SET status = 'failed', error_message = 'Release rejected by user', updated_at = ? WHERE task_id = ? AND status = 'awaiting_release'", (ts, release["task_id"]))

    conn.commit()
    conn.close()
    print(json.dumps({"release_id": release_id, "status": status}))
```

- [ ] **Step 4: Register all three commands in the COMMANDS dict**

Add to the `COMMANDS` dict:

```python
    "create-release": cmd_create_release,
    "list-releases": cmd_list_releases,
    "update-release": cmd_update_release,
```

- [ ] **Step 5: Update the module docstring**

Add to the docstring at the top of the file:

```
  python db-utils.py create-release --task-id <id> --agent-id <id> --title "..." --action-type execute
  python db-utils.py list-releases [--status pending] [--agent planner] [--level 1]
  python db-utils.py update-release <release_id> --status approved
```

- [ ] **Step 6: Test the new commands**

```bash
python scripts/db-init.py
python scripts/db-utils.py list-releases --status pending
```

- [ ] **Step 7: Commit**

```bash
git add scripts/db-utils.py
git commit -m "feat: add work release commands to db-utils (create, list, update)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Build the HTTP Release Server

**Files:**
- Create: `scripts/release-server.py`

- [ ] **Step 1: Create the release server**

```python
#!/usr/bin/env python3
"""Work Release HTTP server — serves the approval UI and REST API.

Usage:
  python scripts/release-server.py [--port 53800]
"""

import http.server
import json
import os
import sqlite3
import sys
import uuid
import urllib.parse
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ultra.db")
UI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
PORT = 53800


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class ReleaseHandler(http.server.BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, filepath, content_type):
        try:
            with open(filepath, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static files
        if path == "/" or path == "/index.html":
            self.send_file(os.path.join(UI_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/style.css":
            self.send_file(os.path.join(UI_DIR, "style.css"), "text/css; charset=utf-8")
        elif path == "/app.js":
            self.send_file(os.path.join(UI_DIR, "app.js"), "application/javascript; charset=utf-8")

        # API: List releases
        elif path == "/api/releases":
            status_filter = query.get("status", [None])[0]
            conn = get_conn()
            if status_filter:
                rows = conn.execute("""
                    SELECT wr.*, a.agent_name, a.agent_type
                    FROM work_releases wr
                    LEFT JOIN agents a ON wr.agent_id = a.agent_id
                    WHERE wr.status = ?
                    ORDER BY wr.agent_level ASC, wr.created_at DESC
                """, (status_filter,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT wr.*, a.agent_name, a.agent_type
                    FROM work_releases wr
                    LEFT JOIN agents a ON wr.agent_id = a.agent_id
                    ORDER BY wr.agent_level ASC, wr.created_at DESC
                """).fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])

        # API: List auto-release rules
        elif path == "/api/rules":
            conn = get_conn()
            rows = conn.execute("SELECT * FROM auto_release_rules ORDER BY created_at DESC").fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])

        # API: System status
        elif path == "/api/status":
            conn = get_conn()
            running = conn.execute("SELECT COUNT(*) as c FROM agents WHERE status = 'running'").fetchone()["c"]
            pending = conn.execute("SELECT COUNT(*) as c FROM work_releases WHERE status = 'pending'").fetchone()["c"]
            queue = conn.execute("SELECT COUNT(*) as c FROM tasks WHERE status IN ('pending', 'assigned')").fetchone()["c"]
            rules = conn.execute("SELECT COUNT(*) as c FROM auto_release_rules WHERE is_enabled = 1").fetchone()["c"]
            total_approved = conn.execute("SELECT COUNT(*) as c FROM work_releases WHERE status = 'approved'").fetchone()["c"]
            total_rejected = conn.execute("SELECT COUNT(*) as c FROM work_releases WHERE status = 'rejected'").fetchone()["c"]
            total_auto = conn.execute("SELECT COUNT(*) as c FROM work_releases WHERE status = 'auto_released'").fetchone()["c"]
            conn.close()
            self.send_json({
                "running_agents": running,
                "pending_releases": pending,
                "queue_depth": queue,
                "active_rules": rules,
                "total_approved": total_approved,
                "total_rejected": total_rejected,
                "total_auto_released": total_auto,
            })

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Parse release ID from path: /api/releases/<id>/<action>
        parts = path.strip("/").split("/")

        # POST /api/releases/<id>/approve
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "releases" and parts[3] == "approve":
            release_id = parts[2]
            ts = now_iso()
            conn = get_conn()
            release = conn.execute("SELECT task_id FROM work_releases WHERE release_id = ?", (release_id,)).fetchone()
            if not release:
                conn.close()
                return self.send_json({"error": "Release not found"}, 404)
            conn.execute("UPDATE work_releases SET status = 'approved', reviewed_at = ? WHERE release_id = ?", (ts, release_id))
            conn.execute("UPDATE tasks SET status = 'in_progress', updated_at = ? WHERE task_id = ? AND status = 'awaiting_release'", (ts, release["task_id"]))
            conn.commit()
            conn.close()
            self.send_json({"release_id": release_id, "status": "approved"})

        # POST /api/releases/<id>/reject
        elif len(parts) == 4 and parts[0] == "api" and parts[1] == "releases" and parts[3] == "reject":
            release_id = parts[2]
            ts = now_iso()
            conn = get_conn()
            release = conn.execute("SELECT task_id FROM work_releases WHERE release_id = ?", (release_id,)).fetchone()
            if not release:
                conn.close()
                return self.send_json({"error": "Release not found"}, 404)
            conn.execute("UPDATE work_releases SET status = 'rejected', reviewed_at = ? WHERE release_id = ?", (ts, release_id))
            conn.execute("UPDATE tasks SET status = 'failed', error_message = 'Release rejected by user', updated_at = ? WHERE task_id = ? AND status = 'awaiting_release'", (ts, release["task_id"]))
            conn.commit()
            conn.close()
            self.send_json({"release_id": release_id, "status": "rejected"})

        # POST /api/releases/<id>/auto-release
        elif len(parts) == 4 and parts[0] == "api" and parts[1] == "releases" and parts[3] == "auto-release":
            release_id = parts[2]
            ts = now_iso()
            conn = get_conn()
            release = conn.execute("""
                SELECT wr.*, a.agent_type
                FROM work_releases wr
                LEFT JOIN agents a ON wr.agent_id = a.agent_id
                WHERE wr.release_id = ?
            """, (release_id,)).fetchone()
            if not release:
                conn.close()
                return self.send_json({"error": "Release not found"}, 404)

            # Approve the release
            conn.execute("UPDATE work_releases SET status = 'approved', reviewed_at = ? WHERE release_id = ?", (ts, release_id))
            conn.execute("UPDATE tasks SET status = 'in_progress', updated_at = ? WHERE task_id = ? AND status = 'awaiting_release'", (ts, release["task_id"]))

            # Create auto-release rule from this release
            rule_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO auto_release_rules (rule_id, match_agent_type, match_action_type, created_from_release_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (rule_id, release["agent_type"] or "*", release["action_type"], release_id, ts))

            conn.commit()
            conn.close()
            self.send_json({"release_id": release_id, "status": "approved", "rule_id": rule_id})

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        parts = path.strip("/").split("/")

        # DELETE /api/rules/<id>
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "rules":
            rule_id = parts[2]
            conn = get_conn()
            conn.execute("DELETE FROM auto_release_rules WHERE rule_id = ?", (rule_id,))
            conn.commit()
            conn.close()
            self.send_json({"deleted": rule_id})
        else:
            self.send_json({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        sys.stderr.write(f"[release-server] {self.address_string()} - {format % args}\n")


def main():
    port = PORT
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}. Run: python scripts/db-init.py", file=sys.stderr)
        sys.exit(1)

    server = http.server.HTTPServer(("0.0.0.0", port), ReleaseHandler)
    print(f"Work Release server running on http://localhost:{port}")
    print(f"Database: {DB_PATH}")
    print(f"UI directory: {UI_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the server starts**

```bash
python scripts/release-server.py &
sleep 2
curl -s http://localhost:53800/api/status
kill %1
```

- [ ] **Step 3: Commit**

```bash
git add scripts/release-server.py
git commit -m "feat: add Work Release HTTP server with REST API on port 53800

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Build the Dashboard HTML

**Files:**
- Create: `ui/index.html`

- [ ] **Step 1: Create the dashboard**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ultra Agent — Work Release</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <header>
        <div class="header-left">
            <h1>Work Release</h1>
            <span class="subtitle">Ultra Agent System</span>
        </div>
        <div class="status-bar" id="status-bar">
            <div class="status-item">
                <span class="status-label">Running</span>
                <span class="status-value" id="stat-running">-</span>
            </div>
            <div class="status-item">
                <span class="status-label">Pending</span>
                <span class="status-value pending" id="stat-pending">-</span>
            </div>
            <div class="status-item">
                <span class="status-label">Queue</span>
                <span class="status-value" id="stat-queue">-</span>
            </div>
            <div class="status-item">
                <span class="status-label">Auto-Rules</span>
                <span class="status-value" id="stat-rules">-</span>
            </div>
        </div>
    </header>

    <main>
        <!-- Filter bar -->
        <div class="filter-bar">
            <div class="filter-group">
                <label>Status:</label>
                <select id="filter-status">
                    <option value="pending" selected>Pending</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                    <option value="auto_released">Auto-Released</option>
                    <option value="">All</option>
                </select>
            </div>
            <div class="filter-group">
                <label>
                    <input type="checkbox" id="auto-refresh" checked>
                    Auto-refresh (5s)
                </label>
            </div>
            <div class="batch-actions">
                <button class="btn btn-approve-all" id="btn-approve-all" title="Approve all pending releases">Approve All</button>
            </div>
        </div>

        <!-- Releases table -->
        <div id="releases-container">
            <div class="loading">Loading releases...</div>
        </div>

        <!-- Auto-Release Rules -->
        <section class="rules-section">
            <div class="rules-header" id="rules-toggle">
                <h2>Auto-Release Rules</h2>
                <span class="toggle-icon" id="rules-toggle-icon">&#9654;</span>
            </div>
            <div class="rules-body" id="rules-body" style="display:none;">
                <table class="rules-table" id="rules-table">
                    <thead>
                        <tr>
                            <th>Agent Type</th>
                            <th>Action Type</th>
                            <th>Title Pattern</th>
                            <th>Times Fired</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="rules-tbody">
                    </tbody>
                </table>
                <div class="rules-empty" id="rules-empty">No auto-release rules configured.</div>
            </div>
        </section>
    </main>

    <footer>
        <span id="last-updated">Never updated</span>
        <span class="footer-stats">
            Approved: <span id="stat-approved">0</span> |
            Rejected: <span id="stat-rejected">0</span> |
            Auto-Released: <span id="stat-auto">0</span>
        </span>
    </footer>

    <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add ui/index.html
git commit -m "feat: add Work Release dashboard HTML

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Build the Dashboard Styling

**Files:**
- Create: `ui/style.css`

- [ ] **Step 1: Create the stylesheet**

```css
/* === Reset & Base === */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
    --bg-primary: #0f1117;
    --bg-secondary: #1a1d27;
    --bg-tertiary: #242836;
    --border: #2e3348;
    --text-primary: #e4e6f0;
    --text-secondary: #8b8fa8;
    --text-muted: #5c6078;
    --accent: #6366f1;
    --accent-hover: #818cf8;
    --green: #22c55e;
    --green-bg: rgba(34, 197, 94, 0.12);
    --green-border: rgba(34, 197, 94, 0.3);
    --red: #ef4444;
    --red-bg: rgba(239, 68, 68, 0.12);
    --red-border: rgba(239, 68, 68, 0.3);
    --yellow: #eab308;
    --yellow-bg: rgba(234, 179, 8, 0.12);
    --yellow-border: rgba(234, 179, 8, 0.3);
    --blue: #3b82f6;
    --blue-bg: rgba(59, 130, 246, 0.12);
    --blue-border: rgba(59, 130, 246, 0.3);
    --purple: #a855f7;
    --purple-bg: rgba(168, 85, 247, 0.12);
    --purple-border: rgba(168, 85, 247, 0.3);
    --radius: 8px;
    --radius-sm: 4px;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.5;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

/* === Header === */
header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
}

.header-left {
    display: flex;
    align-items: baseline;
    gap: 12px;
}

header h1 {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
}

.subtitle {
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 400;
}

.status-bar {
    display: flex;
    gap: 20px;
}

.status-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
}

.status-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
}

.status-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
}

.status-value.pending {
    color: var(--yellow);
}

/* === Main === */
main {
    flex: 1;
    padding: 20px 24px;
    max-width: 1400px;
    width: 100%;
    margin: 0 auto;
}

/* === Filter Bar === */
.filter-bar {
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 16px;
    padding: 12px 16px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
}

.filter-group {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-secondary);
}

.filter-group select {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 4px 8px;
    font-size: 13px;
    cursor: pointer;
}

.filter-group input[type="checkbox"] {
    accent-color: var(--accent);
}

.batch-actions {
    margin-left: auto;
}

/* === Buttons === */
.btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.15s ease;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

.btn:hover { filter: brightness(1.15); }
.btn:active { transform: scale(0.97); }

.btn-approve {
    background: var(--green-bg);
    color: var(--green);
    border-color: var(--green-border);
}

.btn-reject {
    background: var(--red-bg);
    color: var(--red);
    border-color: var(--red-border);
}

.btn-auto {
    background: var(--blue-bg);
    color: var(--blue);
    border-color: var(--blue-border);
}

.btn-approve-all {
    background: var(--green-bg);
    color: var(--green);
    border-color: var(--green-border);
}

.btn-delete {
    background: var(--red-bg);
    color: var(--red);
    border-color: var(--red-border);
    padding: 4px 10px;
    font-size: 11px;
}

.btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

/* === Level Groups === */
.level-group {
    margin-bottom: 20px;
}

.level-group h3 {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-muted);
    margin-bottom: 8px;
    padding-left: 4px;
}

/* === Releases Table === */
.releases-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
}

.releases-table thead th {
    text-align: left;
    padding: 10px 14px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border);
}

.releases-table tbody td {
    padding: 10px 14px;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
}

.releases-table tbody tr:last-child td {
    border-bottom: none;
}

.releases-table tbody tr:hover {
    background: rgba(99, 102, 241, 0.04);
}

/* === Badges === */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

.badge-pending { background: var(--yellow-bg); color: var(--yellow); border: 1px solid var(--yellow-border); }
.badge-approved { background: var(--green-bg); color: var(--green); border: 1px solid var(--green-border); }
.badge-rejected { background: var(--red-bg); color: var(--red); border: 1px solid var(--red-border); }
.badge-auto_released { background: var(--purple-bg); color: var(--purple); border: 1px solid var(--purple-border); }

.badge-level {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    border: 1px solid var(--border);
    font-size: 10px;
    padding: 1px 6px;
}

.badge-action {
    background: var(--blue-bg);
    color: var(--blue);
    border: 1px solid var(--blue-border);
    font-size: 10px;
    padding: 1px 6px;
}

/* === Preview Text === */
.preview-text {
    max-width: 280px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-secondary);
    font-size: 12px;
}

/* === Action Buttons Cell === */
.actions-cell {
    display: flex;
    gap: 6px;
}

/* === Empty & Loading States === */
.loading, .empty-state {
    text-align: center;
    padding: 48px 20px;
    color: var(--text-muted);
    font-size: 14px;
}

.empty-state {
    background: var(--bg-secondary);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
}

/* === Rules Section === */
.rules-section {
    margin-top: 32px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
}

.rules-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    cursor: pointer;
    user-select: none;
}

.rules-header:hover {
    background: rgba(99, 102, 241, 0.04);
}

.rules-header h2 {
    font-size: 14px;
    font-weight: 600;
}

.toggle-icon {
    font-size: 12px;
    color: var(--text-muted);
    transition: transform 0.2s;
}

.toggle-icon.open {
    transform: rotate(90deg);
}

.rules-body {
    border-top: 1px solid var(--border);
    padding: 16px;
}

.rules-table {
    width: 100%;
    border-collapse: collapse;
}

.rules-table thead th {
    text-align: left;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border);
}

.rules-table tbody td {
    padding: 8px 12px;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
}

.rules-empty {
    text-align: center;
    padding: 20px;
    color: var(--text-muted);
    font-size: 13px;
}

/* === Footer === */
footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 24px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border);
    font-size: 12px;
    color: var(--text-muted);
}

.footer-stats {
    font-variant-numeric: tabular-nums;
}

/* === Responsive === */
@media (max-width: 900px) {
    header {
        flex-direction: column;
        gap: 12px;
        align-items: flex-start;
    }
    .filter-bar {
        flex-wrap: wrap;
    }
    .batch-actions {
        margin-left: 0;
    }
    .preview-text {
        max-width: 120px;
    }
}

@media (max-width: 600px) {
    .status-bar {
        gap: 12px;
    }
    main {
        padding: 12px;
    }
    .releases-table thead th,
    .releases-table tbody td {
        padding: 8px 8px;
        font-size: 12px;
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/style.css
git commit -m "feat: add Work Release dashboard dark theme CSS

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Build the Dashboard JavaScript

**Files:**
- Create: `ui/app.js`

- [ ] **Step 1: Create the application logic**

```javascript
/* Work Release Dashboard — vanilla JS */
(function () {
    "use strict";

    const API = "";
    let refreshTimer = null;
    const REFRESH_INTERVAL = 5000;

    // ---- Helpers ----

    async function api(method, path, body) {
        const opts = { method, headers: {} };
        if (body) {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(body);
        }
        const res = await fetch(API + path, opts);
        return res.json();
    }

    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }

    function timeAgo(iso) {
        if (!iso) return "-";
        const diff = (Date.now() - new Date(iso).getTime()) / 1000;
        if (diff < 60) return Math.floor(diff) + "s ago";
        if (diff < 3600) return Math.floor(diff / 60) + "m ago";
        if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
        return Math.floor(diff / 86400) + "d ago";
    }

    function escHtml(str) {
        if (!str) return "";
        const d = document.createElement("div");
        d.textContent = str;
        return d.innerHTML;
    }

    // ---- Status Bar ----

    async function refreshStatus() {
        try {
            const s = await api("GET", "/api/status");
            $("#stat-running").textContent = s.running_agents;
            $("#stat-pending").textContent = s.pending_releases;
            $("#stat-queue").textContent = s.queue_depth;
            $("#stat-rules").textContent = s.active_rules;
            $("#stat-approved").textContent = s.total_approved;
            $("#stat-rejected").textContent = s.total_rejected;
            $("#stat-auto").textContent = s.total_auto_released;
        } catch (e) {
            console.error("Status fetch failed:", e);
        }
    }

    // ---- Releases ----

    function groupByLevel(releases) {
        const groups = {};
        for (const r of releases) {
            const lvl = r.agent_level;
            if (!groups[lvl]) groups[lvl] = [];
            groups[lvl].push(r);
        }
        return groups;
    }

    const LEVEL_NAMES = {
        0: "L0 — Director",
        1: "L1 — Agents",
        2: "L2 — Sub-Agents",
        3: "L3 — Workers",
    };

    function renderReleases(releases) {
        const container = $("#releases-container");

        if (!releases.length) {
            const status = $("#filter-status").value;
            container.innerHTML = '<div class="empty-state">No ' + (status || "matching") + ' releases found.</div>';
            return;
        }

        const groups = groupByLevel(releases);
        let html = "";

        for (const level of [0, 1, 2, 3]) {
            const items = groups[level];
            if (!items || !items.length) continue;

            html += '<div class="level-group">';
            html += '<h3>' + escHtml(LEVEL_NAMES[level] || "Level " + level) + " (" + items.length + ")</h3>";
            html += '<table class="releases-table"><thead><tr>';
            html += "<th>Title</th><th>Agent</th><th>Action</th><th>Input</th><th>Status</th><th>Created</th><th>Actions</th>";
            html += "</tr></thead><tbody>";

            for (const r of items) {
                html += "<tr>";
                html += '<td>' + escHtml(r.title) + '</td>';
                html += '<td>' + escHtml(r.agent_name || r.agent_id) + ' <span class="badge badge-level">L' + r.agent_level + '</span></td>';
                html += '<td><span class="badge badge-action">' + escHtml(r.action_type) + '</span></td>';
                html += '<td><span class="preview-text" title="' + escHtml(r.input_preview) + '">' + escHtml(r.input_preview) + '</span></td>';
                html += '<td><span class="badge badge-' + r.status + '">' + escHtml(r.status) + '</span></td>';
                html += '<td>' + timeAgo(r.created_at) + '</td>';
                html += '<td class="actions-cell">';

                if (r.status === "pending") {
                    html += '<button class="btn btn-approve" data-id="' + r.release_id + '" data-action="approve">Approve</button>';
                    html += '<button class="btn btn-reject" data-id="' + r.release_id + '" data-action="reject">Reject</button>';
                    html += '<button class="btn btn-auto" data-id="' + r.release_id + '" data-action="auto-release" title="Approve + create auto-release rule">Auto</button>';
                }

                html += "</td></tr>";
            }

            html += "</tbody></table></div>";
        }

        container.innerHTML = html;

        // Bind action buttons
        container.querySelectorAll(".btn[data-action]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                handleAction(btn.dataset.id, btn.dataset.action);
            });
        });
    }

    async function loadReleases() {
        const status = $("#filter-status").value;
        const query = status ? "?status=" + encodeURIComponent(status) : "";
        try {
            const releases = await api("GET", "/api/releases" + query);
            renderReleases(releases);
            $("#last-updated").textContent = "Updated " + new Date().toLocaleTimeString();
        } catch (e) {
            $("#releases-container").innerHTML = '<div class="empty-state">Failed to load releases. Is the server running?</div>';
        }
    }

    async function handleAction(releaseId, action) {
        try {
            await api("POST", "/api/releases/" + releaseId + "/" + action);
            await Promise.all([loadReleases(), refreshStatus()]);
        } catch (e) {
            console.error("Action failed:", e);
        }
    }

    // ---- Batch Operations ----

    async function approveAll() {
        const btns = $$("#releases-container .btn-approve");
        if (!btns.length) return;
        if (!confirm("Approve all " + btns.length + " pending releases?")) return;

        const ids = Array.from(btns).map(function (b) { return b.dataset.id; });
        for (const id of ids) {
            await api("POST", "/api/releases/" + id + "/approve");
        }
        await Promise.all([loadReleases(), refreshStatus()]);
    }

    // ---- Auto-Release Rules ----

    async function loadRules() {
        try {
            const rules = await api("GET", "/api/rules");
            const tbody = $("#rules-tbody");
            const empty = $("#rules-empty");

            if (!rules.length) {
                tbody.innerHTML = "";
                empty.style.display = "block";
                return;
            }

            empty.style.display = "none";
            let html = "";
            for (const rule of rules) {
                html += "<tr>";
                html += "<td>" + escHtml(rule.match_agent_type) + "</td>";
                html += "<td>" + escHtml(rule.match_action_type) + "</td>";
                html += "<td>" + escHtml(rule.match_title_pattern || "*") + "</td>";
                html += "<td>" + rule.fire_count + "</td>";
                html += "<td>" + timeAgo(rule.created_at) + "</td>";
                html += '<td><button class="btn btn-delete" data-rule-id="' + rule.rule_id + '">Delete</button></td>';
                html += "</tr>";
            }
            tbody.innerHTML = html;

            tbody.querySelectorAll(".btn-delete").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    deleteRule(btn.dataset.ruleId);
                });
            });
        } catch (e) {
            console.error("Rules fetch failed:", e);
        }
    }

    async function deleteRule(ruleId) {
        if (!confirm("Delete this auto-release rule?")) return;
        try {
            await api("DELETE", "/api/rules/" + ruleId);
            await Promise.all([loadRules(), refreshStatus()]);
        } catch (e) {
            console.error("Delete rule failed:", e);
        }
    }

    // ---- Auto-Refresh ----

    function startRefresh() {
        stopRefresh();
        refreshTimer = setInterval(function () {
            loadReleases();
            refreshStatus();
        }, REFRESH_INTERVAL);
    }

    function stopRefresh() {
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
    }

    // ---- Init ----

    function init() {
        // Filter change
        $("#filter-status").addEventListener("change", function () {
            loadReleases();
        });

        // Auto-refresh toggle
        $("#auto-refresh").addEventListener("change", function () {
            if (this.checked) {
                startRefresh();
            } else {
                stopRefresh();
            }
        });

        // Batch approve
        $("#btn-approve-all").addEventListener("click", approveAll);

        // Rules toggle
        $("#rules-toggle").addEventListener("click", function () {
            const body = $("#rules-body");
            const icon = $("#rules-toggle-icon");
            if (body.style.display === "none") {
                body.style.display = "block";
                icon.classList.add("open");
                loadRules();
            } else {
                body.style.display = "none";
                icon.classList.remove("open");
            }
        });

        // Initial load
        refreshStatus();
        loadReleases();
        startRefresh();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
```

- [ ] **Step 2: Verify the full stack**

```bash
python scripts/release-server.py &
sleep 2
curl -s http://localhost:53800/ | head -5
curl -s http://localhost:53800/api/status
curl -s http://localhost:53800/api/releases?status=pending
kill %1
```

- [ ] **Step 3: Commit all UI files**

```bash
git add ui/index.html ui/style.css ui/app.js
git commit -m "feat: add Work Release dashboard UI (HTML, CSS, JS)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Integration Notes

- **Task lifecycle:** When an agent creates a work release, it sets the task status to `awaiting_release`. On approve, the server flips it to `in_progress`. On reject, it goes to `failed`.
- **Auto-release matching:** `create-release` checks rules on insert. Matching releases skip the pending state entirely and go straight to `auto_released`.
- **Cron Manager (Phase 5):** The cron tick loop should check for `auto_released` and `approved` releases the same way it checks for `in_progress` tasks.
- **Port 53800:** Matches the `.claude/launch.json` configuration. Override with `--port` flag.
- **No external dependencies:** Everything uses Python stdlib and vanilla JS. No npm, no pip installs.
