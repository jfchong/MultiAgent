#!/usr/bin/env python3
"""CLI utility for querying and updating the Ultra Agent database.

Usage:
  python db-utils.py query "SELECT * FROM agents"
  python db-utils.py get-agent planner
  python db-utils.py get-task <task_id>
  python db-utils.py list-tasks [--status pending] [--agent planner]
  python db-utils.py create-task --title "..." --description "..." --assigned planner [--priority 3]
  python db-utils.py update-task <task_id> --status in_progress
  python db-utils.py get-config <key>
  python db-utils.py set-config <key> <value>
"""

import sqlite3
import json
import uuid
import sys
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ultra.db")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row):
    return dict(row) if row else None


def cmd_query(args):
    sql = args[0]
    conn = get_conn()
    rows = conn.execute(sql).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))


def cmd_get_agent(args):
    conn = get_conn()
    row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (args[0],)).fetchone()
    conn.close()
    print(json.dumps(dict_from_row(row), indent=2))


def cmd_get_task(args):
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (args[0],)).fetchone()
    conn.close()
    print(json.dumps(dict_from_row(row), indent=2))


def cmd_list_tasks(args):
    conditions = []
    params = []
    i = 0
    while i < len(args):
        if args[i] == "--status":
            conditions.append("status = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--agent":
            conditions.append("assigned_agent = ?")
            params.append(args[i + 1])
            i += 2
        else:
            i += 1

    sql = "SELECT * FROM tasks"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY priority ASC, created_at DESC"

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))


def cmd_create_task(args):
    title = description = assigned = None
    priority = 5
    created_by = "director"
    i = 0
    while i < len(args):
        if args[i] == "--title":
            title = args[i + 1]; i += 2
        elif args[i] == "--description":
            description = args[i + 1]; i += 2
        elif args[i] == "--assigned":
            assigned = args[i + 1]; i += 2
        elif args[i] == "--priority":
            priority = int(args[i + 1]); i += 2
        elif args[i] == "--created-by":
            created_by = args[i + 1]; i += 2
        else:
            i += 1

    if not title:
        print("Error: --title is required", file=sys.stderr)
        sys.exit(1)

    task_id = str(uuid.uuid4())
    ts = now_iso()
    status = "assigned" if assigned else "pending"

    conn = get_conn()
    conn.execute("""
        INSERT INTO tasks (task_id, title, description, status, priority, assigned_agent, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (task_id, title, description, status, priority, assigned, created_by, ts, ts))
    conn.commit()
    conn.close()

    print(json.dumps({"task_id": task_id, "status": status}))


def cmd_update_task(args):
    task_id = args[0]
    updates = {}
    i = 1
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:].replace("-", "_")
            updates[key] = args[i + 1]
            i += 2
        else:
            i += 1

    if not updates:
        print("Error: no updates specified", file=sys.stderr)
        sys.exit(1)

    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [task_id]

    conn = get_conn()
    conn.execute(f"UPDATE tasks SET {set_clause} WHERE task_id = ?", params)
    conn.commit()
    conn.close()
    print(json.dumps({"task_id": task_id, "updated": list(updates.keys())}))


def cmd_get_config(args):
    conn = get_conn()
    row = conn.execute("SELECT value FROM config WHERE key = ?", (args[0],)).fetchone()
    conn.close()
    print(row["value"] if row else "")


def cmd_set_config(args):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (args[0], args[1]))
    conn.commit()
    conn.close()
    print(json.dumps({"key": args[0], "value": args[1]}))


def cmd_list_sessions(args):
    conditions = []
    params = []
    i = 0
    while i < len(args):
        if args[i] == "--status":
            conditions.append("status = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--agent":
            conditions.append("agent_id = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--task":
            conditions.append("task_id = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--success":
            conditions.append("success = ?")
            params.append(int(args[i + 1]))
            i += 2
        elif args[i] == "--browser":
            conditions.append("browser_category IS NOT NULL")
            i += 1
        elif args[i] == "--limit":
            i += 2
        else:
            i += 1

    sql = "SELECT * FROM sessions"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY started_at DESC"

    limit = 50
    for j in range(len(args)):
        if args[j] == "--limit" and j + 1 < len(args):
            limit = int(args[j + 1])
    sql += f" LIMIT {limit}"

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))


def cmd_get_session(args):
    session_id = args[0]
    conn = get_conn()
    session = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    recordings = conn.execute(
        "SELECT * FROM session_recordings WHERE session_id = ? ORDER BY step_number",
        (session_id,)
    ).fetchall()
    conn.close()
    result = dict_from_row(session) if session else None
    if result:
        result["recordings"] = [dict(r) for r in recordings]
    print(json.dumps(result, indent=2))


def cmd_create_credential(args):
    site_domain = label = auth_type = None
    creds = {}
    i = 0
    while i < len(args):
        if args[i] == "--domain":
            site_domain = args[i + 1]; i += 2
        elif args[i] == "--label":
            label = args[i + 1]; i += 2
        elif args[i] == "--auth-type":
            auth_type = args[i + 1]; i += 2
        elif args[i] == "--username":
            creds["username"] = args[i + 1]; i += 2
        elif args[i] == "--password":
            creds["password"] = args[i + 1]; i += 2
        elif args[i] == "--api-key":
            creds["api_key"] = args[i + 1]; i += 2
        else:
            i += 1

    if not site_domain or not label:
        print("Error: --domain and --label are required", file=sys.stderr)
        sys.exit(1)

    credential_id = str(uuid.uuid4())
    ts = now_iso()
    if not auth_type:
        auth_type = "password"

    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO credentials (credential_id, site_domain, label, auth_type, credentials_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (credential_id, site_domain, label, auth_type, json.dumps(creds), ts, ts))
    conn.commit()
    conn.close()
    print(json.dumps({"credential_id": credential_id, "site_domain": site_domain}))


def cmd_list_credentials(args):
    conn = get_conn()
    rows = conn.execute("SELECT credential_id, site_domain, label, auth_type, created_at, updated_at FROM credentials ORDER BY site_domain").fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))


def cmd_delete_credential(args):
    site_domain = args[0]
    conn = get_conn()
    conn.execute("DELETE FROM credentials WHERE site_domain = ?", (site_domain,))
    conn.commit()
    conn.close()
    print(json.dumps({"deleted": site_domain}))


COMMANDS = {
    "query": cmd_query,
    "get-agent": cmd_get_agent,
    "get-task": cmd_get_task,
    "list-tasks": cmd_list_tasks,
    "create-task": cmd_create_task,
    "update-task": cmd_update_task,
    "get-config": cmd_get_config,
    "set-config": cmd_set_config,
    "list-sessions": cmd_list_sessions,
    "get-session": cmd_get_session,
    "create-credential": cmd_create_credential,
    "list-credentials": cmd_list_credentials,
    "delete-credential": cmd_delete_credential,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python db-utils.py <command> [args]")
        print(f"Commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
