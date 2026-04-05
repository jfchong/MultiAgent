#!/usr/bin/env python3
"""Ultra Agent Dashboard HTTP server.

Replaces release-server.py. Serves the React dashboard SPA from
dashboard/dist/ and provides a comprehensive JSON API for all
dashboard features.

Usage:
    python scripts/dashboard-server.py [--port PORT] [--db PATH]
"""

import argparse
import json
import logging
import mimetypes
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "ultra.db")
DEFAULT_PORT = 53800
DIST_DIR = os.path.join(BASE_DIR, "dashboard", "dist")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("dashboard-server")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_start_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")


def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Route matching helpers
# ---------------------------------------------------------------------------

def match_route(pattern: str, path: str):
    """Match a URL pattern like '/api/tasks/:id/timeline' against a path.
    Returns a dict of captured params or None if no match."""
    regex = re.sub(r':(\w+)', r'(?P<\1>[^/]+)', pattern)
    m = re.fullmatch(regex, path)
    return m.groupdict() if m else None


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Ultra Agent Dashboard."""

    db_path: str = DEFAULT_DB

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, data, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message: str, status: int = 400):
        self._json_response({"error": message}, status)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _serve_static(self, file_path: str):
        """Serve a static file from the dashboard dist directory."""
        if not os.path.isfile(file_path):
            return False
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = "application/octet-stream"
        with open(file_path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)
        return True

    def _serve_index(self):
        """Serve the SPA index.html for client-side routing."""
        index_path = os.path.join(DIST_DIR, "index.html")
        if os.path.isfile(index_path):
            with open(index_path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        else:
            self._error("Dashboard not built. Run: cd dashboard && npm run build", 404)

    def _qs_int(self, qs, key, default):
        try:
            return int(qs.get(key, [default])[0])
        except (ValueError, IndexError):
            return default

    def _qs_str(self, qs, key, default=None):
        vals = qs.get(key, [default])
        return vals[0] if vals else default

    def log_message(self, fmt, *args):
        log.info("%s - %s", self.address_string(), fmt % args)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        # --- API routes ---
        if path.startswith("/api/"):
            self._route_get_api(path, qs)
            return

        # --- Static file serving from dashboard/dist ---
        if path == "/":
            self._serve_index()
            return

        # Try to serve static file
        # Strip leading slash and normalize path to prevent directory traversal
        rel_path = path.lstrip("/")
        file_path = os.path.normpath(os.path.join(DIST_DIR, rel_path))
        if file_path.startswith(os.path.normpath(DIST_DIR)):
            if self._serve_static(file_path):
                return

        # SPA fallback: serve index.html for all non-API, non-static routes
        self._serve_index()

    def _route_get_api(self, path, qs):
        """Route GET /api/* requests."""
        # System
        if path == "/api/status":
            return self._api_status(qs)
        if path == "/api/activity":
            return self._api_activity(qs)
        if path == "/api/pipeline":
            return self._api_pipeline()

        # Requests
        if path == "/api/requests":
            return self._api_list_requests(qs)

        # Tasks
        if path == "/api/tasks":
            return self._api_list_tasks(qs)
        m = match_route("/api/tasks/:id/timeline", path)
        if m:
            return self._api_task_timeline(m["id"])
        m = match_route("/api/tasks/:id/subtasks", path)
        if m:
            return self._api_task_subtasks(m["id"])
        m = match_route("/api/tasks/:id", path)
        if m:
            return self._api_task_detail(m["id"])

        # Agents
        if path == "/api/agents/hierarchy":
            return self._api_agents_hierarchy()
        if path == "/api/agents":
            return self._api_list_agents()
        m = match_route("/api/agents/:id/sessions", path)
        if m:
            return self._api_agent_sessions(m["id"], qs)
        m = match_route("/api/agents/:id", path)
        if m:
            return self._api_agent_detail(m["id"])

        # Releases (backward compatible)
        if path == "/api/releases":
            return self._api_list_releases(qs)
        if path == "/api/rules":
            return self._api_list_rules()

        # Skills
        if path == "/api/skills":
            return self._api_list_skills(qs)
        m = match_route("/api/skills/:id/invocations", path)
        if m:
            return self._api_skill_invocations(m["id"], qs)
        m = match_route("/api/skills/:id", path)
        if m:
            return self._api_skill_detail(m["id"])

        # Sessions
        if path == "/api/sessions":
            return self._api_list_sessions(qs)
        m = match_route("/api/sessions/:id/recordings", path)
        if m:
            return self._api_session_recordings(m["id"])
        m = match_route("/api/sessions/:id", path)
        if m:
            return self._api_session_detail(m["id"])

        # Improvements
        if path == "/api/improvements/stats":
            return self._api_improvement_stats()
        if path == "/api/improvements":
            return self._api_list_improvements(qs)

        # Settings
        if path == "/api/config":
            return self._api_list_config()
        if path == "/api/credentials":
            return self._api_list_credentials()
        if path == "/api/cron":
            return self._api_list_cron()

        self._error("Not found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Requests
        if path == "/api/requests":
            return self._api_create_request()

        # Releases (backward compatible)
        m = match_route("/api/releases/:id/approve", path)
        if m:
            return self._api_approve_release(m["id"])
        m = match_route("/api/releases/:id/reject", path)
        if m:
            return self._api_reject_release(m["id"])
        m = match_route("/api/releases/:id/auto-release", path)
        if m:
            return self._api_auto_release(m["id"])

        # Credentials
        if path == "/api/credentials":
            return self._api_create_credential()

        # Cron
        if path == "/api/cron":
            return self._api_create_cron()

        self._error("Not found", 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Config
        m = match_route("/api/config/:key", path)
        if m:
            return self._api_update_config(m["key"])

        # Cron
        m = match_route("/api/cron/:id", path)
        if m:
            return self._api_update_cron(m["id"])

        self._error("Not found", 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Rules (backward compatible)
        m = match_route("/api/rules/:id", path)
        if m:
            return self._api_delete_rule(m["id"])

        # Credentials
        m = match_route("/api/credentials/:id", path)
        if m:
            return self._api_delete_credential(m["id"])

        # Cron
        m = match_route("/api/cron/:id", path)
        if m:
            return self._api_delete_cron(m["id"])

        self._error("Not found", 404)

    # ==================================================================
    # API implementations — System
    # ==================================================================

    def _api_status(self, qs):
        """GET /api/status — KPI metrics for overview page."""
        conn = get_db(self.db_path)
        try:
            running_agents = conn.execute(
                "SELECT COUNT(*) FROM agents WHERE status = 'running'"
            ).fetchone()[0]

            total_agents = conn.execute(
                "SELECT COUNT(*) FROM agents"
            ).fetchone()[0]

            pending_tasks = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'pending'"
            ).fetchone()[0]

            pending_releases = conn.execute(
                "SELECT COUNT(*) FROM work_releases WHERE status = 'pending'"
            ).fetchone()[0]

            today = today_start_iso()
            completed_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'completed' AND completed_at >= ?",
                (today,)
            ).fetchone()[0]

            completed_all = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'completed'"
            ).fetchone()[0]
            failed_all = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'failed'"
            ).fetchone()[0]
            total_finished = completed_all + failed_all
            success_rate = round(completed_all / total_finished, 2) if total_finished > 0 else 1.0

            task_rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM tasks GROUP BY status"
            ).fetchall()
            tasks_by_status = {r["status"]: r["cnt"] for r in task_rows}

            total_tasks = conn.execute(
                "SELECT COUNT(*) FROM tasks"
            ).fetchone()[0]

            active_rules = conn.execute(
                "SELECT COUNT(*) FROM auto_release_rules WHERE is_enabled = 1"
            ).fetchone()[0]

            assigned_tasks = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'assigned'"
            ).fetchone()[0]
        finally:
            conn.close()

        self._json_response({
            "running_agents": running_agents,
            "total_agents": total_agents,
            "pending_tasks": pending_tasks,
            "assigned_tasks": assigned_tasks,
            "pending_releases": pending_releases,
            "active_rules": active_rules,
            "completed_today": completed_today,
            "success_rate": success_rate,
            "total_tasks": total_tasks,
            "tasks_by_status": tasks_by_status,
        })

    def _api_activity(self, qs):
        """GET /api/activity — Recent activity feed."""
        limit = self._qs_int(qs, "limit", 50)
        conn = get_db(self.db_path)
        try:
            rows = conn.execute("""
                SELECT
                    e.event_id AS id,
                    'event' AS type,
                    e.event_type,
                    e.agent_id,
                    a.agent_name,
                    e.task_id,
                    t.title AS task_title,
                    e.data_json,
                    e.created_at AS timestamp
                FROM events e
                LEFT JOIN agents a ON a.agent_id = e.agent_id
                LEFT JOIN tasks t ON t.task_id = e.task_id
                ORDER BY e.created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            result = []
            for r in rows:
                item = dict(r)
                try:
                    item["data"] = json.loads(item.pop("data_json", "{}"))
                except (json.JSONDecodeError, TypeError):
                    item["data"] = {}
                # Build a human-readable summary
                evt = item.get("event_type", "")
                agent = item.get("agent_name") or item.get("agent_id") or "System"
                task_title = item.get("task_title") or ""
                if evt == "user_request":
                    item["summary"] = f"User submitted request: {task_title}"
                elif evt == "task_assigned":
                    item["summary"] = f"{agent} assigned to task"
                elif evt == "task_completed":
                    item["summary"] = f"{agent} completed task: {task_title}"
                elif evt == "task_failed":
                    item["summary"] = f"{agent} failed task: {task_title}"
                elif evt == "agent_started":
                    item["summary"] = f"{agent} started"
                elif evt == "agent_completed":
                    item["summary"] = f"{agent} completed"
                elif evt == "release_created":
                    item["summary"] = f"{agent} created work release"
                elif evt == "release_approved":
                    item["summary"] = f"Release approved for {agent}"
                elif evt == "release_rejected":
                    item["summary"] = f"Release rejected for {agent}"
                else:
                    item["summary"] = f"{agent}: {evt}"
                result.append(item)
        finally:
            conn.close()
        self._json_response(result)

    def _api_pipeline(self):
        """GET /api/pipeline — Task counts by status."""
        conn = get_db(self.db_path)
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM tasks GROUP BY status"
            ).fetchall()
            pipeline = {
                "pending": 0, "assigned": 0, "awaiting_release": 0,
                "in_progress": 0, "blocked": 0, "review": 0,
                "completed": 0, "failed": 0, "cancelled": 0,
            }
            for r in rows:
                pipeline[r["status"]] = r["cnt"]
        finally:
            conn.close()
        self._json_response(pipeline)

    # ==================================================================
    # API implementations — Requests
    # ==================================================================

    def _api_create_request(self):
        """POST /api/requests — Submit a new user request."""
        body = self._read_body()
        title = body.get("title", "").strip()
        description = body.get("description", "").strip()
        priority = body.get("priority", 5)

        if not title:
            return self._error("title is required")

        if not isinstance(priority, int) or priority < 1 or priority > 10:
            priority = 5

        conn = get_db(self.db_path)
        try:
            task_id = str(uuid.uuid4())
            ts = now_iso()

            conn.execute("""
                INSERT INTO tasks (task_id, title, description, status, priority,
                                  assigned_agent, created_by, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, 'director', 'user', ?, ?)
            """, (task_id, title[:120], description or title, priority, ts, ts))

            conn.execute("""
                INSERT INTO events (event_id, event_type, agent_id, task_id, data_json, created_at)
                VALUES (?, 'user_request', 'director', ?, ?, ?)
            """, (str(uuid.uuid4()), task_id, json.dumps({"title": title, "description": description}), ts))

            conn.commit()
        finally:
            conn.close()

        log.info("Request submitted: %s (%s)", task_id, title[:60])
        self._json_response({"ok": True, "task_id": task_id, "status": "pending"}, 201)

    def _api_list_requests(self, qs):
        """GET /api/requests — List user-submitted requests."""
        limit = self._qs_int(qs, "limit", 50)
        offset = self._qs_int(qs, "offset", 0)
        conn = get_db(self.db_path)
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE created_by = 'user'"
            ).fetchone()[0]

            rows = conn.execute("""
                SELECT t.task_id, t.title, t.description, t.status, t.priority,
                       t.created_at, t.completed_at, t.output_data,
                       (SELECT COUNT(*) FROM tasks sub WHERE sub.parent_task_id = t.task_id) AS subtask_count,
                       (SELECT COUNT(*) FROM tasks sub WHERE sub.parent_task_id = t.task_id AND sub.status = 'completed') AS completed_subtask_count
                FROM tasks t
                WHERE t.created_by = 'user'
                ORDER BY t.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
        finally:
            conn.close()
        self._json_response({"items": rows_to_list(rows), "total": total})

    # ==================================================================
    # API implementations — Tasks
    # ==================================================================

    def _api_list_tasks(self, qs):
        """GET /api/tasks — List tasks with filters."""
        limit = self._qs_int(qs, "limit", 100)
        offset = self._qs_int(qs, "offset", 0)
        status_filter = self._qs_str(qs, "status")
        agent_filter = self._qs_str(qs, "agent")
        priority_min = self._qs_int(qs, "priority_min", 1)
        priority_max = self._qs_int(qs, "priority_max", 10)
        parent_task_id = self._qs_str(qs, "parent_task_id")
        search = self._qs_str(qs, "search")

        where_clauses = ["t.priority BETWEEN ? AND ?"]
        params = [priority_min, priority_max]

        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",")]
            placeholders = ",".join(["?"] * len(statuses))
            where_clauses.append(f"t.status IN ({placeholders})")
            params.extend(statuses)

        if agent_filter:
            where_clauses.append("t.assigned_agent = ?")
            params.append(agent_filter)

        if parent_task_id:
            where_clauses.append("t.parent_task_id = ?")
            params.append(parent_task_id)

        if search:
            where_clauses.append("t.title LIKE ?")
            params.append(f"%{search}%")

        where_sql = " AND ".join(where_clauses)

        conn = get_db(self.db_path)
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM tasks t WHERE {where_sql}", params
            ).fetchone()[0]

            rows = conn.execute(f"""
                SELECT t.task_id, t.parent_task_id, t.title, t.status, t.priority,
                       t.assigned_agent, a.agent_name, t.created_by, t.framework,
                       t.created_at, t.started_at, t.completed_at,
                       CASE WHEN t.started_at IS NOT NULL AND t.completed_at IS NOT NULL
                            THEN ROUND((julianday(t.completed_at) - julianday(t.started_at)) * 86400, 1)
                            ELSE NULL END AS duration_seconds
                FROM tasks t
                LEFT JOIN agents a ON a.agent_id = t.assigned_agent
                WHERE {where_sql}
                ORDER BY t.created_at DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset]).fetchall()
        finally:
            conn.close()
        self._json_response({"items": rows_to_list(rows), "total": total})

    def _api_task_detail(self, task_id):
        """GET /api/tasks/:id — Full task detail."""
        conn = get_db(self.db_path)
        try:
            row = conn.execute("""
                SELECT t.*, a.agent_name
                FROM tasks t
                LEFT JOIN agents a ON a.agent_id = t.assigned_agent
                WHERE t.task_id = ?
            """, (task_id,)).fetchone()
            if not row:
                return self._error("Task not found", 404)
            result = dict(row)
        finally:
            conn.close()
        self._json_response(result)

    def _api_task_timeline(self, task_id):
        """GET /api/tasks/:id/timeline — Events for this task."""
        conn = get_db(self.db_path)
        try:
            rows = conn.execute("""
                SELECT e.event_id, e.event_type, e.agent_id, a.agent_name,
                       e.data_json, e.created_at AS timestamp
                FROM events e
                LEFT JOIN agents a ON a.agent_id = e.agent_id
                WHERE e.task_id = ?
                ORDER BY e.created_at ASC
            """, (task_id,)).fetchall()
            result = []
            for r in rows:
                item = dict(r)
                try:
                    item["data"] = json.loads(item.pop("data_json", "{}"))
                except (json.JSONDecodeError, TypeError):
                    item["data"] = {}
                result.append(item)
        finally:
            conn.close()
        self._json_response(result)

    def _api_task_subtasks(self, task_id):
        """GET /api/tasks/:id/subtasks — Recursive subtask tree."""
        conn = get_db(self.db_path)
        try:
            # Fetch all descendants using recursive CTE
            rows = conn.execute("""
                WITH RECURSIVE subtree AS (
                    SELECT t.task_id, t.parent_task_id, t.title, t.status,
                           t.assigned_agent, t.priority, t.created_at, t.completed_at
                    FROM tasks t WHERE t.parent_task_id = ?
                    UNION ALL
                    SELECT t.task_id, t.parent_task_id, t.title, t.status,
                           t.assigned_agent, t.priority, t.created_at, t.completed_at
                    FROM tasks t
                    JOIN subtree s ON t.parent_task_id = s.task_id
                )
                SELECT s.*, a.agent_name
                FROM subtree s
                LEFT JOIN agents a ON a.agent_id = s.assigned_agent
                ORDER BY s.created_at ASC
            """, (task_id,)).fetchall()
            all_tasks = [dict(r) for r in rows]
        finally:
            conn.close()

        # Build tree structure
        by_parent = {}
        for t in all_tasks:
            parent = t["parent_task_id"]
            by_parent.setdefault(parent, []).append(t)

        def build_tree(parent_id):
            children = by_parent.get(parent_id, [])
            for child in children:
                child["children"] = build_tree(child["task_id"])
            return children

        tree = build_tree(task_id)
        self._json_response(tree)

    # ==================================================================
    # API implementations — Agents
    # ==================================================================

    def _api_list_agents(self):
        """GET /api/agents — All agents with status and counts."""
        conn = get_db(self.db_path)
        try:
            rows = conn.execute("""
                SELECT a.agent_id, a.agent_name, a.agent_type, a.level,
                       a.parent_agent_id, a.status, a.run_count, a.error_count,
                       a.last_run_at,
                       (SELECT COUNT(*) FROM tasks t
                        WHERE t.assigned_agent = a.agent_id
                        AND t.status IN ('assigned','in_progress')) AS active_task_count
                FROM agents a
                ORDER BY a.level, a.agent_name
            """).fetchall()
            result = []
            for r in rows:
                item = dict(r)
                total = item["run_count"] or 0
                errors = item["error_count"] or 0
                item["success_rate"] = round((total - errors) / total, 2) if total > 0 else 1.0
                result.append(item)
        finally:
            conn.close()
        self._json_response(result)

    def _api_agent_detail(self, agent_id):
        """GET /api/agents/:id — Agent detail with task history."""
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if not row:
                return self._error("Agent not found", 404)
            result = dict(row)
            total = result.get("run_count", 0) or 0
            errors = result.get("error_count", 0) or 0
            result["success_rate"] = round((total - errors) / total, 2) if total > 0 else 1.0

            # Current task
            current = conn.execute("""
                SELECT task_id, title, status
                FROM tasks
                WHERE assigned_agent = ? AND status IN ('assigned', 'in_progress')
                ORDER BY updated_at DESC LIMIT 1
            """, (agent_id,)).fetchone()
            result["current_task"] = dict(current) if current else None

            # Recent tasks
            recent = conn.execute("""
                SELECT task_id, title, status, started_at, completed_at
                FROM tasks
                WHERE assigned_agent = ? AND status IN ('completed', 'failed')
                ORDER BY completed_at DESC LIMIT 10
            """, (agent_id,)).fetchall()
            result["recent_tasks"] = rows_to_list(recent)
        finally:
            conn.close()
        self._json_response(result)

    def _api_agent_sessions(self, agent_id, qs):
        """GET /api/agents/:id/sessions — Agent's session history."""
        limit = self._qs_int(qs, "limit", 20)
        offset = self._qs_int(qs, "offset", 0)
        conn = get_db(self.db_path)
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE agent_id = ?", (agent_id,)
            ).fetchone()[0]

            rows = conn.execute("""
                SELECT s.session_id, s.task_id, t.title AS task_title,
                       s.browser_category, s.status, s.success,
                       s.started_at, s.completed_at, s.duration_seconds, s.summary
                FROM sessions s
                LEFT JOIN tasks t ON t.task_id = s.task_id
                WHERE s.agent_id = ?
                ORDER BY s.started_at DESC
                LIMIT ? OFFSET ?
            """, (agent_id, limit, offset)).fetchall()
        finally:
            conn.close()
        self._json_response({"items": rows_to_list(rows), "total": total})

    def _api_agents_hierarchy(self):
        """GET /api/agents/hierarchy — Tree structure for agent hierarchy."""
        conn = get_db(self.db_path)
        try:
            rows = conn.execute("""
                SELECT agent_id, agent_name, agent_type, level,
                       parent_agent_id, status, run_count, error_count
                FROM agents
                ORDER BY level, agent_name
            """).fetchall()
            all_agents = [dict(r) for r in rows]
        finally:
            conn.close()

        by_parent = {}
        for a in all_agents:
            parent = a.get("parent_agent_id")
            by_parent.setdefault(parent, []).append(a)

        def build_tree(parent_id):
            children = by_parent.get(parent_id, [])
            for child in children:
                child["children"] = build_tree(child["agent_id"])
            return children

        # Root is the agent with no parent (Director)
        roots = by_parent.get(None, [])
        if roots:
            root = roots[0]
            root["children"] = build_tree(root["agent_id"])
            self._json_response(root)
        else:
            self._json_response({})

    # ==================================================================
    # API implementations — Releases (backward compatible)
    # ==================================================================

    def _api_list_releases(self, qs):
        """GET /api/releases?status=pending"""
        status_filter = self._qs_str(qs, "status")
        conn = get_db(self.db_path)
        try:
            sql = """
                SELECT
                    wr.release_id, wr.task_id, wr.agent_id, wr.agent_level,
                    wr.title, wr.description, wr.action_type,
                    wr.input_preview, wr.output_preview,
                    wr.status, wr.auto_release, wr.auto_release_rule_id,
                    wr.reviewed_at, wr.created_at,
                    a.agent_name, a.agent_type,
                    t.title AS task_title, t.status AS task_status
                FROM work_releases wr
                LEFT JOIN agents a ON a.agent_id = wr.agent_id
                LEFT JOIN tasks  t ON t.task_id  = wr.task_id
            """
            params = []
            if status_filter:
                sql += " WHERE wr.status = ?"
                params.append(status_filter)
            sql += " ORDER BY wr.created_at DESC"
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        self._json_response(rows_to_list(rows))

    def _api_approve_release(self, release_id):
        """POST /api/releases/:id/approve"""
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT release_id, task_id, status FROM work_releases WHERE release_id = ?",
                (release_id,)
            ).fetchone()
            if not row:
                return self._error("Release not found", 404)
            if row["status"] != "pending":
                return self._error(f"Release is already '{row['status']}'", 409)

            ts = now_iso()
            conn.execute(
                "UPDATE work_releases SET status='approved', reviewed_at=? WHERE release_id=?",
                (ts, release_id)
            )
            conn.execute(
                "UPDATE tasks SET status='in_progress', updated_at=? WHERE task_id=? AND status='awaiting_release'",
                (ts, row["task_id"])
            )
            conn.commit()
            log.info("Approved release %s (task %s)", release_id, row["task_id"])
        finally:
            conn.close()
        self._json_response({"ok": True, "release_id": release_id, "status": "approved"})

    def _api_reject_release(self, release_id):
        """POST /api/releases/:id/reject"""
        body = self._read_body()
        reason = body.get("reason", "")
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT release_id, task_id, status FROM work_releases WHERE release_id = ?",
                (release_id,)
            ).fetchone()
            if not row:
                return self._error("Release not found", 404)
            if row["status"] != "pending":
                return self._error(f"Release is already '{row['status']}'", 409)

            ts = now_iso()
            conn.execute(
                "UPDATE work_releases SET status='rejected', reviewed_at=? WHERE release_id=?",
                (ts, release_id)
            )
            conn.execute(
                """UPDATE tasks SET status='failed', error_message=?, updated_at=?
                   WHERE task_id=? AND status='awaiting_release'""",
                (reason or "Rejected via Work Release UI", ts, row["task_id"])
            )
            conn.commit()
            log.info("Rejected release %s (task %s): %s", release_id, row["task_id"], reason)
        finally:
            conn.close()
        self._json_response({"ok": True, "release_id": release_id, "status": "rejected"})

    def _api_auto_release(self, release_id):
        """POST /api/releases/:id/auto-release — approve + create rule."""
        body = self._read_body()
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                """SELECT wr.release_id, wr.task_id, wr.agent_id, wr.action_type, wr.status,
                          a.agent_type
                   FROM work_releases wr
                   LEFT JOIN agents a ON a.agent_id = wr.agent_id
                   WHERE wr.release_id = ?""",
                (release_id,)
            ).fetchone()
            if not row:
                return self._error("Release not found", 404)
            if row["status"] != "pending":
                return self._error(f"Release is already '{row['status']}'", 409)

            ts = now_iso()
            rule_id = str(uuid.uuid4())

            match_agent_type = body.get("match_agent_type", row["agent_type"] or "*")
            match_action_type = body.get("match_action_type", row["action_type"] or "*")
            match_skill_id = body.get("match_skill_id", None)
            match_title_pat = body.get("match_title_pattern", None)

            conn.execute(
                """INSERT INTO auto_release_rules
                   (rule_id, match_agent_type, match_action_type, match_skill_id,
                    match_title_pattern, is_enabled, created_from_release_id, fire_count, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, 0, ?)""",
                (rule_id, match_agent_type, match_action_type, match_skill_id,
                 match_title_pat, release_id, ts)
            )

            conn.execute(
                """UPDATE work_releases
                   SET status='auto_released', auto_release=1, auto_release_rule_id=?, reviewed_at=?
                   WHERE release_id=?""",
                (rule_id, ts, release_id)
            )

            conn.execute(
                "UPDATE tasks SET status='in_progress', updated_at=? WHERE task_id=? AND status='awaiting_release'",
                (ts, row["task_id"])
            )
            conn.commit()
            log.info(
                "Auto-release rule %s created from release %s (agent_type=%s, action_type=%s)",
                rule_id, release_id, match_agent_type, match_action_type
            )
        finally:
            conn.close()
        self._json_response({
            "ok": True,
            "release_id": release_id,
            "status": "auto_released",
            "rule_id": rule_id,
        })

    def _api_list_rules(self):
        """GET /api/rules"""
        conn = get_db(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM auto_release_rules ORDER BY created_at DESC"
            ).fetchall()
        finally:
            conn.close()
        self._json_response(rows_to_list(rows))

    def _api_delete_rule(self, rule_id):
        """DELETE /api/rules/:id"""
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT rule_id FROM auto_release_rules WHERE rule_id = ?", (rule_id,)
            ).fetchone()
            if not row:
                return self._error("Rule not found", 404)
            conn.execute("DELETE FROM auto_release_rules WHERE rule_id = ?", (rule_id,))
            conn.commit()
            log.info("Deleted auto-release rule %s", rule_id)
        finally:
            conn.close()
        self._json_response({"ok": True, "rule_id": rule_id, "deleted": True})

    # ==================================================================
    # API implementations — Skills
    # ==================================================================

    def _api_list_skills(self, qs):
        """GET /api/skills — List skills with search and filter."""
        limit = self._qs_int(qs, "limit", 100)
        offset = self._qs_int(qs, "offset", 0)
        search = self._qs_str(qs, "search")
        category = self._qs_str(qs, "category")
        namespace = self._qs_str(qs, "namespace")
        active_only = self._qs_str(qs, "active_only", "true")

        where_clauses = []
        params = []

        if active_only.lower() == "true":
            where_clauses.append("s.is_active = 1")

        if search:
            where_clauses.append("(s.skill_name LIKE ? OR s.description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        if category:
            where_clauses.append("s.category = ?")
            params.append(category)

        if namespace:
            where_clauses.append("s.namespace = ?")
            params.append(namespace)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        conn = get_db(self.db_path)
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM skill_registry s{where_sql}", params
            ).fetchone()[0]

            rows = conn.execute(f"""
                SELECT s.skill_id, s.skill_name, s.namespace, s.category,
                       s.description, s.success_count, s.failure_count,
                       s.version, s.is_active, s.last_used_at, s.created_at
                FROM skill_registry s
                {where_sql}
                ORDER BY s.last_used_at DESC NULLS LAST
                LIMIT ? OFFSET ?
            """, params + [limit, offset]).fetchall()

            result = []
            for r in rows:
                item = dict(r)
                sc = item.get("success_count", 0) or 0
                fc = item.get("failure_count", 0) or 0
                total_inv = sc + fc
                item["success_rate"] = round(sc / total_inv, 2) if total_inv > 0 else 1.0
                result.append(item)
        finally:
            conn.close()
        self._json_response({"items": result, "total": total})

    def _api_skill_detail(self, skill_id):
        """GET /api/skills/:id — Full skill detail."""
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM skill_registry WHERE skill_id = ?", (skill_id,)
            ).fetchone()
            if not row:
                return self._error("Skill not found", 404)
            result = dict(row)
            # Parse JSON fields
            for field in ["data_schema", "output_schema", "tools_required"]:
                try:
                    result[field] = json.loads(result.get(field, "{}"))
                except (json.JSONDecodeError, TypeError):
                    pass
        finally:
            conn.close()
        self._json_response(result)

    def _api_skill_invocations(self, skill_id, qs):
        """GET /api/skills/:id/invocations — Invocation history."""
        limit = self._qs_int(qs, "limit", 20)
        offset = self._qs_int(qs, "offset", 0)
        conn = get_db(self.db_path)
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM skill_invocations WHERE skill_id = ?", (skill_id,)
            ).fetchone()[0]

            rows = conn.execute("""
                SELECT si.invocation_id, si.task_id, si.agent_id,
                       si.input_data, si.output_data, si.status,
                       si.duration_seconds, si.error_message,
                       si.created_at, si.completed_at
                FROM skill_invocations si
                WHERE si.skill_id = ?
                ORDER BY si.created_at DESC
                LIMIT ? OFFSET ?
            """, (skill_id, limit, offset)).fetchall()
        finally:
            conn.close()
        self._json_response({"items": rows_to_list(rows), "total": total})

    # ==================================================================
    # API implementations — Sessions
    # ==================================================================

    def _api_list_sessions(self, qs):
        """GET /api/sessions — List sessions with filters."""
        limit = self._qs_int(qs, "limit", 50)
        offset = self._qs_int(qs, "offset", 0)
        agent = self._qs_str(qs, "agent")
        status = self._qs_str(qs, "status")
        browser_cat = self._qs_str(qs, "browser_category")
        success = self._qs_str(qs, "success")

        where_clauses = []
        params = []

        if agent:
            where_clauses.append("s.agent_id = ?")
            params.append(agent)
        if status:
            where_clauses.append("s.status = ?")
            params.append(status)
        if browser_cat:
            where_clauses.append("s.browser_category = ?")
            params.append(browser_cat)
        if success is not None and success in ("0", "1", "true", "false"):
            val = 1 if success in ("1", "true") else 0
            where_clauses.append("s.success = ?")
            params.append(val)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        conn = get_db(self.db_path)
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM sessions s{where_sql}", params
            ).fetchone()[0]

            rows = conn.execute(f"""
                SELECT s.session_id, s.agent_id, a.agent_name,
                       s.task_id, t.title AS task_title,
                       s.browser_category, s.status, s.success,
                       s.started_at, s.completed_at, s.duration_seconds, s.summary
                FROM sessions s
                LEFT JOIN agents a ON a.agent_id = s.agent_id
                LEFT JOIN tasks t ON t.task_id = s.task_id
                {where_sql}
                ORDER BY s.started_at DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset]).fetchall()
        finally:
            conn.close()
        self._json_response({"items": rows_to_list(rows), "total": total})

    def _api_session_detail(self, session_id):
        """GET /api/sessions/:id — Session detail with recordings."""
        conn = get_db(self.db_path)
        try:
            row = conn.execute("""
                SELECT s.*, a.agent_name, t.title AS task_title
                FROM sessions s
                LEFT JOIN agents a ON a.agent_id = s.agent_id
                LEFT JOIN tasks t ON t.task_id = s.task_id
                WHERE s.session_id = ?
            """, (session_id,)).fetchone()
            if not row:
                return self._error("Session not found", 404)
            result = dict(row)

            recordings = conn.execute("""
                SELECT * FROM session_recordings
                WHERE session_id = ?
                ORDER BY step_number ASC
            """, (session_id,)).fetchall()
            result["recordings"] = rows_to_list(recordings)
        finally:
            conn.close()
        self._json_response(result)

    def _api_session_recordings(self, session_id):
        """GET /api/sessions/:id/recordings — Step-by-step action log."""
        conn = get_db(self.db_path)
        try:
            rows = conn.execute("""
                SELECT * FROM session_recordings
                WHERE session_id = ?
                ORDER BY step_number ASC
            """, (session_id,)).fetchall()
        finally:
            conn.close()
        self._json_response(rows_to_list(rows))

    # ==================================================================
    # API implementations — Improvements
    # ==================================================================

    def _api_list_improvements(self, qs):
        """GET /api/improvements — List improvement log entries."""
        limit = self._qs_int(qs, "limit", 50)
        offset = self._qs_int(qs, "offset", 0)
        category = self._qs_str(qs, "category")
        agent = self._qs_str(qs, "agent")

        where_clauses = []
        params = []

        if category:
            where_clauses.append("il.category = ?")
            params.append(category)
        if agent:
            where_clauses.append("il.agent_id = ?")
            params.append(agent)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        conn = get_db(self.db_path)
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM improvement_log il{where_sql}", params
            ).fetchone()[0]

            rows = conn.execute(f"""
                SELECT il.log_id, il.task_id, t.title AS task_title,
                       il.agent_id, a.agent_name, il.category, il.summary,
                       il.details, il.impact_score, il.action_taken, il.created_at
                FROM improvement_log il
                LEFT JOIN agents a ON a.agent_id = il.agent_id
                LEFT JOIN tasks t ON t.task_id = il.task_id
                {where_sql}
                ORDER BY il.created_at DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset]).fetchall()
        finally:
            conn.close()
        self._json_response({"items": rows_to_list(rows), "total": total})

    def _api_improvement_stats(self):
        """GET /api/improvements/stats — Aggregated improvement metrics."""
        conn = get_db(self.db_path)
        try:
            total_patterns = conn.execute(
                "SELECT COUNT(*) FROM improvement_log"
            ).fetchone()[0]

            avg_impact = conn.execute(
                "SELECT AVG(impact_score) FROM improvement_log WHERE impact_score IS NOT NULL"
            ).fetchone()[0] or 0.0

            cat_rows = conn.execute("""
                SELECT category, COUNT(*) AS count, AVG(impact_score) AS avg_impact
                FROM improvement_log
                GROUP BY category
            """).fetchall()
            by_category = {}
            for r in cat_rows:
                by_category[r["category"]] = {
                    "count": r["count"],
                    "avg_impact": round(r["avg_impact"] or 0, 2)
                }

            agent_rows = conn.execute("""
                SELECT il.agent_id, a.agent_name, COUNT(*) AS count,
                       AVG(il.impact_score) AS avg_impact
                FROM improvement_log il
                LEFT JOIN agents a ON a.agent_id = il.agent_id
                GROUP BY il.agent_id
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            top_agents = []
            for r in agent_rows:
                top_agents.append({
                    "agent_id": r["agent_id"],
                    "agent_name": r["agent_name"],
                    "count": r["count"],
                    "avg_impact": round(r["avg_impact"] or 0, 2)
                })
        finally:
            conn.close()

        self._json_response({
            "total_patterns": total_patterns,
            "avg_impact_score": round(avg_impact, 2),
            "by_category": by_category,
            "top_improving_agents": top_agents,
        })

    # ==================================================================
    # API implementations — Settings
    # ==================================================================

    def _api_list_config(self):
        """GET /api/config — All config key-value pairs."""
        conn = get_db(self.db_path)
        try:
            rows = conn.execute("SELECT key, value FROM config ORDER BY key").fetchall()
        finally:
            conn.close()
        self._json_response(rows_to_list(rows))

    def _api_update_config(self, key):
        """PUT /api/config/:key — Update a config value."""
        body = self._read_body()
        value = body.get("value")
        if value is None:
            return self._error("value is required")
        conn = get_db(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            conn.commit()
        finally:
            conn.close()
        self._json_response({"ok": True, "key": key, "value": str(value)})

    def _api_list_credentials(self):
        """GET /api/credentials — List credentials (never exposes secrets)."""
        conn = get_db(self.db_path)
        try:
            rows = conn.execute("""
                SELECT credential_id, site_domain, label, auth_type,
                       created_at, updated_at
                FROM credentials
                ORDER BY label
            """).fetchall()
        finally:
            conn.close()
        self._json_response(rows_to_list(rows))

    def _api_create_credential(self):
        """POST /api/credentials — Add a new credential."""
        body = self._read_body()
        site_domain = body.get("site_domain", "").strip()
        label = body.get("label", "").strip()
        auth_type = body.get("auth_type", "password")
        creds_json = body.get("credentials_json", {})

        if not site_domain or not label:
            return self._error("site_domain and label are required")

        conn = get_db(self.db_path)
        try:
            cred_id = str(uuid.uuid4())
            ts = now_iso()
            conn.execute("""
                INSERT INTO credentials (credential_id, site_domain, label, auth_type,
                                        credentials_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cred_id, site_domain, label, auth_type, json.dumps(creds_json), ts, ts))
            conn.commit()
        finally:
            conn.close()
        self._json_response({"ok": True, "credential_id": cred_id}, 201)

    def _api_delete_credential(self, cred_id):
        """DELETE /api/credentials/:id — Delete a credential."""
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT credential_id FROM credentials WHERE credential_id = ?", (cred_id,)
            ).fetchone()
            if not row:
                return self._error("Credential not found", 404)
            conn.execute("DELETE FROM credentials WHERE credential_id = ?", (cred_id,))
            conn.commit()
        finally:
            conn.close()
        self._json_response({"ok": True, "credential_id": cred_id, "deleted": True})

    def _api_list_cron(self):
        """GET /api/cron — List all cron schedules."""
        conn = get_db(self.db_path)
        try:
            rows = conn.execute("""
                SELECT cs.*, a.agent_name
                FROM cron_schedule cs
                LEFT JOIN agents a ON a.agent_id = cs.agent_id
                ORDER BY cs.created_at DESC
            """).fetchall()
        finally:
            conn.close()
        self._json_response(rows_to_list(rows))

    def _api_create_cron(self):
        """POST /api/cron — Create a new cron schedule."""
        body = self._read_body()
        agent_id = body.get("agent_id", "").strip()
        cron_expr = body.get("cron_expression", "").strip()
        task_template = body.get("task_template", "")
        is_enabled = 1 if body.get("is_enabled", True) else 0
        max_fires = body.get("max_fires")

        if not agent_id or not cron_expr:
            return self._error("agent_id and cron_expression are required")

        conn = get_db(self.db_path)
        try:
            schedule_id = str(uuid.uuid4())
            ts = now_iso()
            conn.execute("""
                INSERT INTO cron_schedule (schedule_id, agent_id, cron_expression,
                                          task_template, is_enabled, max_fires, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (schedule_id, agent_id, cron_expr, task_template, is_enabled, max_fires, ts))
            conn.commit()
        finally:
            conn.close()
        self._json_response({"ok": True, "schedule_id": schedule_id}, 201)

    def _api_update_cron(self, schedule_id):
        """PUT /api/cron/:id — Update a cron schedule."""
        body = self._read_body()
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT schedule_id FROM cron_schedule WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
            if not row:
                return self._error("Schedule not found", 404)

            updates = []
            params = []
            for field in ["cron_expression", "task_template"]:
                if field in body:
                    updates.append(f"{field} = ?")
                    params.append(body[field])
            if "is_enabled" in body:
                updates.append("is_enabled = ?")
                params.append(1 if body["is_enabled"] else 0)
            if "max_fires" in body:
                updates.append("max_fires = ?")
                params.append(body["max_fires"])

            if updates:
                params.append(schedule_id)
                conn.execute(
                    f"UPDATE cron_schedule SET {', '.join(updates)} WHERE schedule_id = ?",
                    params
                )
                conn.commit()
        finally:
            conn.close()
        self._json_response({"ok": True, "schedule_id": schedule_id})

    def _api_delete_cron(self, schedule_id):
        """DELETE /api/cron/:id — Delete a cron schedule."""
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT schedule_id FROM cron_schedule WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
            if not row:
                return self._error("Schedule not found", 404)
            conn.execute("DELETE FROM cron_schedule WHERE schedule_id = ?", (schedule_id,))
            conn.commit()
        finally:
            conn.close()
        self._json_response({"ok": True, "schedule_id": schedule_id, "deleted": True})


# ---------------------------------------------------------------------------
# Server factory & entry-point
# ---------------------------------------------------------------------------

def make_server(port: int, db_path: str) -> HTTPServer:
    class _Handler(DashboardHandler):
        pass
    _Handler.db_path = db_path
    server = HTTPServer(("", port), _Handler)
    return server


def main():
    parser = argparse.ArgumentParser(description="Ultra Agent Dashboard server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--db", default=DEFAULT_DB,
                        help=f"Path to ultra.db (default: {DEFAULT_DB})")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.isfile(db_path):
        log.warning("Database not found at %s — run db-init.py first", db_path)

    server = make_server(args.port, db_path)
    log.info("Dashboard server listening on http://localhost:%d", args.port)
    log.info("Database: %s", db_path)
    log.info("Static files: %s", DIST_DIR)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
