#!/usr/bin/env python3
"""Work Release HTTP server for the Ultra Agent system.

Serves the Work Release web UI and provides a JSON API for managing
work_releases and auto_release_rules in the Ultra Agent SQLite database.

Usage:
    python scripts/release-server.py [--port PORT] [--db PATH]
"""

import argparse
import json
import logging
import os
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
UI_DIR = os.path.join(BASE_DIR, "ui")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("release-server")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class ReleaseHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Work Release UI and API."""

    db_path: str = DEFAULT_DB  # set by server factory

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
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

    def _serve_file(self, file_path: str, content_type: str):
        if not os.path.isfile(file_path):
            self._error("Not found", 404)
            return
        with open(file_path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # noqa: N802 – override stdlib method
        log.info("%s - %s", self.address_string(), fmt % args)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        # Static files
        if path == "/":
            self._serve_file(os.path.join(UI_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/style.css":
            self._serve_file(os.path.join(UI_DIR, "style.css"), "text/css; charset=utf-8")
        elif path == "/app.js":
            self._serve_file(os.path.join(UI_DIR, "app.js"), "application/javascript; charset=utf-8")

        # API endpoints
        elif path == "/api/releases":
            self._api_list_releases(qs)
        elif path == "/api/rules":
            self._api_list_rules()
        elif path == "/api/status":
            self._api_status()
        else:
            self._error("Not found", 404)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # POST /api/releases/<id>/approve
        if path.startswith("/api/releases/") and path.endswith("/approve"):
            release_id = path[len("/api/releases/"):-len("/approve")]
            self._api_approve_release(release_id)
        # POST /api/releases/<id>/reject
        elif path.startswith("/api/releases/") and path.endswith("/reject"):
            release_id = path[len("/api/releases/"):-len("/reject")]
            self._api_reject_release(release_id)
        # POST /api/releases/<id>/auto-release
        elif path.startswith("/api/releases/") and path.endswith("/auto-release"):
            release_id = path[len("/api/releases/"):-len("/auto-release")]
            self._api_auto_release(release_id)
        else:
            self._error("Not found", 404)

    def do_DELETE(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/rules/"):
            rule_id = path[len("/api/rules/"):]
            self._api_delete_rule(rule_id)
        else:
            self._error("Not found", 404)

    # ------------------------------------------------------------------
    # API implementations
    # ------------------------------------------------------------------

    def _api_list_releases(self, qs: dict):
        """GET /api/releases?status=pending"""
        status_filter = qs.get("status", [None])[0]
        conn = get_db(self.db_path)
        try:
            sql = """
                SELECT
                    wr.release_id,
                    wr.task_id,
                    wr.agent_id,
                    wr.agent_level,
                    wr.title,
                    wr.description,
                    wr.action_type,
                    wr.input_preview,
                    wr.output_preview,
                    wr.status,
                    wr.auto_release,
                    wr.auto_release_rule_id,
                    wr.reviewed_at,
                    wr.created_at,
                    a.agent_name,
                    a.agent_type,
                    t.title AS task_title,
                    t.status AS task_status
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
            result = [dict(r) for r in rows]
        finally:
            conn.close()
        self._json_response(result)

    def _api_approve_release(self, release_id: str):
        """POST /api/releases/<id>/approve"""
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT release_id, task_id, status FROM work_releases WHERE release_id = ?",
                (release_id,),
            ).fetchone()
            if not row:
                self._error("Release not found", 404)
                return
            if row["status"] != "pending":
                self._error(f"Release is already '{row['status']}'", 409)
                return

            ts = now_iso()
            conn.execute(
                "UPDATE work_releases SET status='approved', reviewed_at=? WHERE release_id=?",
                (ts, release_id),
            )
            conn.execute(
                "UPDATE tasks SET status='in_progress', updated_at=? WHERE task_id=? AND status='awaiting_release'",
                (ts, row["task_id"]),
            )
            conn.commit()
            log.info("Approved release %s (task %s)", release_id, row["task_id"])
        finally:
            conn.close()
        self._json_response({"ok": True, "release_id": release_id, "status": "approved"})

    def _api_reject_release(self, release_id: str):
        """POST /api/releases/<id>/reject"""
        body = self._read_body()
        reason = body.get("reason", "")
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT release_id, task_id, status FROM work_releases WHERE release_id = ?",
                (release_id,),
            ).fetchone()
            if not row:
                self._error("Release not found", 404)
                return
            if row["status"] != "pending":
                self._error(f"Release is already '{row['status']}'", 409)
                return

            ts = now_iso()
            conn.execute(
                "UPDATE work_releases SET status='rejected', reviewed_at=? WHERE release_id=?",
                (ts, release_id),
            )
            conn.execute(
                """UPDATE tasks SET status='failed', error_message=?, updated_at=?
                   WHERE task_id=? AND status='awaiting_release'""",
                (reason or "Rejected via Work Release UI", ts, row["task_id"]),
            )
            conn.commit()
            log.info("Rejected release %s (task %s): %s", release_id, row["task_id"], reason)
        finally:
            conn.close()
        self._json_response({"ok": True, "release_id": release_id, "status": "rejected"})

    def _api_auto_release(self, release_id: str):
        """POST /api/releases/<id>/auto-release — approve + create auto_release_rules entry."""
        body = self._read_body()
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                """SELECT wr.release_id, wr.task_id, wr.agent_id, wr.action_type, wr.status,
                          a.agent_type
                   FROM work_releases wr
                   LEFT JOIN agents a ON a.agent_id = wr.agent_id
                   WHERE wr.release_id = ?""",
                (release_id,),
            ).fetchone()
            if not row:
                self._error("Release not found", 404)
                return
            if row["status"] != "pending":
                self._error(f"Release is already '{row['status']}'", 409)
                return

            ts = now_iso()
            rule_id = str(uuid.uuid4())

            # Build rule from body overrides or sensible defaults derived from the release
            match_agent_type  = body.get("match_agent_type",  row["agent_type"] or "*")
            match_action_type = body.get("match_action_type", row["action_type"] or "*")
            match_skill_id    = body.get("match_skill_id",    None)
            match_title_pat   = body.get("match_title_pattern", None)

            conn.execute(
                """INSERT INTO auto_release_rules
                   (rule_id, match_agent_type, match_action_type, match_skill_id,
                    match_title_pattern, is_enabled, created_from_release_id, fire_count, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, 0, ?)""",
                (rule_id, match_agent_type, match_action_type, match_skill_id,
                 match_title_pat, release_id, ts),
            )

            # Mark release as auto_released and link the new rule
            conn.execute(
                """UPDATE work_releases
                   SET status='auto_released', auto_release=1, auto_release_rule_id=?, reviewed_at=?
                   WHERE release_id=?""",
                (rule_id, ts, release_id),
            )

            # Advance the task the same way as a regular approve
            conn.execute(
                "UPDATE tasks SET status='in_progress', updated_at=? WHERE task_id=? AND status='awaiting_release'",
                (ts, row["task_id"]),
            )
            conn.commit()
            log.info(
                "Auto-release rule %s created from release %s (agent_type=%s, action_type=%s)",
                rule_id, release_id, match_agent_type, match_action_type,
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
            result = [dict(r) for r in rows]
        finally:
            conn.close()
        self._json_response(result)

    def _api_delete_rule(self, rule_id: str):
        """DELETE /api/rules/<id>"""
        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT rule_id FROM auto_release_rules WHERE rule_id = ?", (rule_id,)
            ).fetchone()
            if not row:
                self._error("Rule not found", 404)
                return
            conn.execute("DELETE FROM auto_release_rules WHERE rule_id = ?", (rule_id,))
            conn.commit()
            log.info("Deleted auto-release rule %s", rule_id)
        finally:
            conn.close()
        self._json_response({"ok": True, "rule_id": rule_id, "deleted": True})

    def _api_status(self):
        """GET /api/status — system health snapshot."""
        conn = get_db(self.db_path)
        try:
            running_agents = conn.execute(
                "SELECT COUNT(*) FROM agents WHERE status = 'running'"
            ).fetchone()[0]

            pending_releases = conn.execute(
                "SELECT COUNT(*) FROM work_releases WHERE status = 'pending'"
            ).fetchone()[0]

            active_rules = conn.execute(
                "SELECT COUNT(*) FROM auto_release_rules WHERE is_enabled = 1"
            ).fetchone()[0]

            task_rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM tasks GROUP BY status"
            ).fetchall()
            tasks_by_status = {r["status"]: r["cnt"] for r in task_rows}
        finally:
            conn.close()

        self._json_response({
            "running_agents": running_agents,
            "pending_releases": pending_releases,
            "active_rules": active_rules,
            "tasks_by_status": tasks_by_status,
        })


# ---------------------------------------------------------------------------
# Server factory & entry-point
# ---------------------------------------------------------------------------

def make_server(port: int, db_path: str) -> HTTPServer:
    """Create an HTTPServer with the ReleaseHandler configured for *db_path*."""

    # Subclass so each server instance can carry its own db_path without
    # relying on a global variable.
    class _Handler(ReleaseHandler):
        pass

    _Handler.db_path = db_path

    server = HTTPServer(("", port), _Handler)
    return server


def main():
    parser = argparse.ArgumentParser(description="Work Release HTTP server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--db", default=DEFAULT_DB,
                        help=f"Path to ultra.db (default: {DEFAULT_DB})")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.isfile(db_path):
        log.warning("Database not found at %s — start db-init.py first", db_path)

    server = make_server(args.port, db_path)
    log.info("Work Release server listening on http://localhost:%d", args.port)
    log.info("Database: %s", db_path)
    log.info("UI directory: %s", UI_DIR)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
