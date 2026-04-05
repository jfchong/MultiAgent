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


def cmd_create_skill(args):
    name = category = description = template = None
    data_schema = "{}"
    output_schema = "{}"
    tools = "[]"
    i = 0
    while i < len(args):
        if args[i] == "--name":
            name = args[i + 1]; i += 2
        elif args[i] == "--category":
            category = args[i + 1]; i += 2
        elif args[i] == "--description":
            description = args[i + 1]; i += 2
        elif args[i] == "--template":
            template = args[i + 1]; i += 2
        elif args[i] == "--data-schema":
            data_schema = args[i + 1]; i += 2
        elif args[i] == "--output-schema":
            output_schema = args[i + 1]; i += 2
        elif args[i] == "--tools":
            tools = args[i + 1]; i += 2
        else:
            i += 1

    if not name or not category or not description or not template:
        print("Error: --name, --category, --description, and --template are required", file=sys.stderr)
        sys.exit(1)

    conn = get_conn()
    ns_row = conn.execute("SELECT value FROM config WHERE key = 'default_namespace'").fetchone()
    namespace = ns_row["value"] if ns_row else "default"

    skill_id = str(uuid.uuid4())
    ts = now_iso()

    conn.execute("""
        INSERT INTO skill_registry (skill_id, skill_name, namespace, category, description, agent_template, data_schema, output_schema, tools_required, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (skill_id, name, namespace, category, description, template, data_schema, output_schema, tools, ts, ts))
    conn.commit()
    conn.close()
    print(json.dumps({"skill_id": skill_id, "skill_name": name, "namespace": namespace}))


def cmd_list_skills(args):
    conditions = ["is_active = 1"]
    params = []
    i = 0
    while i < len(args):
        if args[i] == "--category":
            conditions.append("category = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--search":
            keyword = args[i + 1]
            conditions.append("(skill_name LIKE ? OR category LIKE ? OR description LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
            i += 2
        elif args[i] == "--namespace":
            conditions.append("namespace = ?")
            params.append(args[i + 1])
            i += 2
        else:
            i += 1

    sql = "SELECT skill_id, skill_name, namespace, category, description, success_count, failure_count, version, last_used_at FROM skill_registry"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY success_count DESC"

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))


def cmd_get_skill(args):
    skill_id = args[0]
    conn = get_conn()
    row = conn.execute("SELECT * FROM skill_registry WHERE skill_id = ?", (skill_id,)).fetchone()
    conn.close()
    print(json.dumps(dict_from_row(row), indent=2))


def cmd_create_invocation(args):
    skill_id = task_id = agent_id = input_data = None
    i = 0
    while i < len(args):
        if args[i] == "--skill-id":
            skill_id = args[i + 1]; i += 2
        elif args[i] == "--task-id":
            task_id = args[i + 1]; i += 2
        elif args[i] == "--agent-id":
            agent_id = args[i + 1]; i += 2
        elif args[i] == "--input-data":
            input_data = args[i + 1]; i += 2
        else:
            i += 1

    if not skill_id or not task_id or not agent_id or not input_data:
        print("Error: --skill-id, --task-id, --agent-id, and --input-data are required", file=sys.stderr)
        sys.exit(1)

    invocation_id = str(uuid.uuid4())
    ts = now_iso()

    conn = get_conn()
    conn.execute("""
        INSERT INTO skill_invocations (invocation_id, skill_id, task_id, agent_id, input_data, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """, (invocation_id, skill_id, task_id, agent_id, input_data, ts))
    conn.execute("UPDATE skill_registry SET last_used_at = ?, updated_at = ? WHERE skill_id = ?", (ts, ts, skill_id))
    conn.commit()
    conn.close()
    print(json.dumps({"invocation_id": invocation_id, "skill_id": skill_id, "task_id": task_id}))


def cmd_update_invocation(args):
    invocation_id = args[0]
    status = output_data = error = None
    i = 1
    while i < len(args):
        if args[i] == "--status":
            status = args[i + 1]; i += 2
        elif args[i] == "--output-data":
            output_data = args[i + 1]; i += 2
        elif args[i] == "--error":
            error = args[i + 1]; i += 2
        else:
            i += 1

    if not status:
        print("Error: --status is required", file=sys.stderr)
        sys.exit(1)

    ts = now_iso()
    conn = get_conn()

    updates = {"status": status, "completed_at": ts}
    if output_data:
        updates["output_data"] = output_data
    if error:
        updates["error_message"] = error

    # Calculate duration
    row = conn.execute("SELECT created_at FROM skill_invocations WHERE invocation_id = ?", (invocation_id,)).fetchone()
    if row:
        try:
            from datetime import datetime as dt
            s = dt.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            e = dt.fromisoformat(ts.replace("Z", "+00:00"))
            updates["duration_seconds"] = (e - s).total_seconds()
        except:
            pass

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [invocation_id]
    conn.execute(f"UPDATE skill_invocations SET {set_clause} WHERE invocation_id = ?", params)

    # Update skill success/failure counts
    inv = conn.execute("SELECT skill_id FROM skill_invocations WHERE invocation_id = ?", (invocation_id,)).fetchone()
    if inv:
        if status == "completed":
            conn.execute("UPDATE skill_registry SET success_count = success_count + 1, updated_at = ? WHERE skill_id = ?", (ts, inv["skill_id"]))
        elif status == "failed":
            conn.execute("UPDATE skill_registry SET failure_count = failure_count + 1, updated_at = ? WHERE skill_id = ?", (ts, inv["skill_id"]))

    conn.commit()
    conn.close()
    print(json.dumps({"invocation_id": invocation_id, "status": status}))


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
    "create-skill": cmd_create_skill,
    "list-skills": cmd_list_skills,
    "get-skill": cmd_get_skill,
    "create-invocation": cmd_create_invocation,
    "update-invocation": cmd_update_invocation,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python db-utils.py <command> [args]")
        print(f"Commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
