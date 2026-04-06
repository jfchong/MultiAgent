#!/usr/bin/env python3
"""Ultra Agent CLI — The front door to the Ultra Agent system.

This is where you tell the system what to do. Your request goes to the
Director (L0), who creates tasks, picks frameworks, and dispatches the
right agents to get it done.

Usage:
  python scripts/ultra.py "Send a reminder email to all unit owners about Q2 payments"
  python scripts/ultra.py --interactive
  python scripts/ultra.py --status
  python scripts/ultra.py --history
"""

import sqlite3
import subprocess
import json
import uuid
import os
import sys
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, "ultra.db")
DB_UTILS = os.path.join(PROJECT_DIR, "scripts", "db-utils.py")
DISPATCH = os.path.join(PROJECT_DIR, "scripts", "dispatch-agent.sh")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def submit_request(prompt, priority=5, background=False):
    """Submit a user request to the Director agent."""
    conn = get_conn()

    # 1. Create the top-level task
    task_id = str(uuid.uuid4())
    ts = now_iso()
    conn.execute("""
        INSERT INTO tasks (task_id, title, description, status, priority,
                          assigned_agent, created_by, created_at, updated_at)
        VALUES (?, ?, ?, 'assigned', ?, 'director', 'user', ?, ?)
    """, (task_id, prompt[:120], prompt, priority, ts, ts))

    # 2. Log the event
    conn.execute("""
        INSERT INTO events (event_id, event_type, agent_id, task_id, data_json, created_at)
        VALUES (?, 'user_request', 'director', ?, ?, ?)
    """, (str(uuid.uuid4()), task_id, json.dumps({"prompt": prompt}), ts))

    conn.commit()
    conn.close()

    print(f"\n  Request submitted!")
    print(f"  Task ID:  {task_id}")
    print(f"  Prompt:   {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    print(f"  Priority: {priority}")
    print()

    # 3. Dispatch the Director
    if background:
        print("  Dispatching Director in background...")
        print("  The Cron Manager will handle downstream agents.")
        print(f"  Monitor at: http://localhost:53800")
        print()
        subprocess.Popen(
            ["bash", DISPATCH, "director", task_id, "sonnet", "--background"],
            cwd=PROJECT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        print("  Dispatching Director (foreground — waiting for response)...")
        print("  " + "=" * 56)
        print()
        result = subprocess.run(
            ["bash", DISPATCH, "director", task_id, "sonnet"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            # Try to pretty-print JSON output
            try:
                data = json.loads(result.stdout)
                print(json.dumps(data, indent=2))
            except json.JSONDecodeError:
                print(result.stdout)
        if result.stderr.strip():
            # Show dispatch logs (non-error)
            for line in result.stderr.strip().split("\n"):
                if line.startswith("[dispatch]"):
                    print(f"  {line}")
        print()

    return task_id


def show_status():
    """Show current system status."""
    conn = get_conn()

    # Running agents
    running = conn.execute(
        "SELECT agent_id, agent_name, agent_type, level FROM agents WHERE status = 'running'"
    ).fetchall()

    # Tasks by status
    task_counts = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status ORDER BY cnt DESC"
    ).fetchall()

    # Pending releases
    pending = conn.execute(
        "SELECT COUNT(*) FROM work_releases WHERE status = 'pending'"
    ).fetchone()[0]

    # Recent completed tasks
    recent = conn.execute("""
        SELECT task_id, title, status, completed_at
        FROM tasks
        WHERE status IN ('completed', 'failed')
        ORDER BY completed_at DESC LIMIT 5
    """).fetchall()

    conn.close()

    print("\n  " + "=" * 56)
    print("  ULTRA AGENT SYSTEM — STATUS")
    print("  " + "=" * 56)

    print(f"\n  Running Agents: {len(running)}")
    for a in running:
        print(f"    L{a['level']} {a['agent_name']} ({a['agent_id']})")

    print(f"\n  Tasks:")
    for t in task_counts:
        print(f"    {t['status']:20s} {t['cnt']}")

    print(f"\n  Pending Releases: {pending}")
    if pending > 0:
        print(f"    Review at: http://localhost:53800")

    if recent:
        print(f"\n  Recent Results:")
        for t in recent:
            icon = "✓" if t["status"] == "completed" else "✗"
            print(f"    {icon} {t['title'][:60]}")

    print()


def show_history(limit=10):
    """Show recent user requests and their outcomes."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT t.task_id, t.title, t.status, t.priority,
               t.created_at, t.completed_at, t.output_data
        FROM tasks t
        WHERE t.created_by = 'user'
        ORDER BY t.created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    print("\n  " + "=" * 56)
    print("  RECENT REQUESTS")
    print("  " + "=" * 56)

    if not rows:
        print("\n  No requests yet. Submit one with:")
        print('  python scripts/ultra.py "Your request here"')
        print()
        return

    for r in rows:
        status_icon = {
            "completed": "✓",
            "failed": "✗",
            "in_progress": "⟳",
            "pending": "○",
            "assigned": "○",
            "awaiting_release": "⏸",
        }.get(r["status"], "?")

        print(f"\n  {status_icon} [{r['status']}] {r['title']}")
        print(f"    ID: {r['task_id']}")
        print(f"    Created: {r['created_at']}")
        if r["completed_at"]:
            print(f"    Completed: {r['completed_at']}")
        if r["output_data"]:
            try:
                out = json.loads(r["output_data"])
                summary = out.get("summary", out.get("result", str(out)[:100]))
                print(f"    Result: {summary}")
            except:
                print(f"    Result: {r['output_data'][:100]}")

    print()


def interactive_mode():
    """Interactive prompt loop."""
    print()
    print("  " + "=" * 56)
    print("  ULTRA AGENT — Interactive Mode")
    print("  " + "=" * 56)
    print()
    print("  Type your requests below. The Director will handle them.")
    print("  Commands:  /status  /history  /quit")
    print()

    while True:
        try:
            prompt = input("  ultra> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if not prompt:
            continue
        elif prompt.lower() in ("/quit", "/exit", "/q"):
            print("  Goodbye!")
            break
        elif prompt.lower() == "/status":
            show_status()
        elif prompt.lower() == "/history":
            show_history()
        else:
            # Check for priority prefix: "!3 do something" sets priority 3
            priority = 5
            if prompt.startswith("!") and len(prompt) > 2 and prompt[1].isdigit():
                priority = int(prompt[1])
                prompt = prompt[3:].strip()

            submit_request(prompt, priority=priority, background=True)


def main():
    if not os.path.exists(DB_PATH):
        print("  [ERROR] Database not found. Run: python scripts/db-init.py")
        sys.exit(1)

    args = sys.argv[1:]

    if not args or args[0] == "--interactive" or args[0] == "-i":
        interactive_mode()
    elif args[0] == "--status" or args[0] == "-s":
        show_status()
    elif args[0] == "--history" or args[0] == "-h":
        show_history()
    elif args[0].startswith("-"):
        print(__doc__)
    else:
        # Direct request: python scripts/ultra.py "Do something"
        prompt = " ".join(args)
        priority = 5

        # Check for --priority flag
        if "--priority" in args:
            idx = args.index("--priority")
            priority = int(args[idx + 1])
            prompt = " ".join(args[:idx])

        # Check for --bg flag
        bg = "--bg" in args or "--background" in args
        if bg:
            prompt = prompt.replace("--bg", "").replace("--background", "").strip()

        submit_request(prompt, priority=priority, background=bg)


if __name__ == "__main__":
    main()
