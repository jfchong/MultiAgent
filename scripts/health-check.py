#!/usr/bin/env python3
"""Health Check — On-demand system health report for the Ultra Agent system.

Usage:
  python scripts/health-check.py           # Full health report
  python scripts/health-check.py --json    # JSON output for programmatic use
"""

import sqlite3
import json
import sys
import os
from datetime import datetime, timezone, timedelta

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, "ultra.db")


def now_utc():
    return datetime.now(timezone.utc)


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def check_health():
    conn = get_conn()
    report = {}

    # --- Agents by status ---
    agent_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM agents GROUP BY status"
    ).fetchall()
    report["agents_by_status"] = {r["status"]: r["cnt"] for r in agent_rows}

    total_agents = conn.execute("SELECT COUNT(*) as cnt FROM agents").fetchone()["cnt"]
    report["agents_total"] = total_agents

    # --- Agents by level ---
    level_rows = conn.execute(
        "SELECT level, COUNT(*) as cnt FROM agents GROUP BY level ORDER BY level"
    ).fetchall()
    report["agents_by_level"] = {f"L{r['level']}": r["cnt"] for r in level_rows}

    # --- Tasks by status ---
    task_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
    ).fetchall()
    report["tasks_by_status"] = {r["status"]: r["cnt"] for r in task_rows}

    total_tasks = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]
    report["tasks_total"] = total_tasks

    # --- Stuck agents (running > configured timeout) ---
    timeout_row = conn.execute(
        "SELECT value FROM config WHERE key = 'stuck_agent_timeout_minutes'"
    ).fetchone()
    timeout_minutes = int(timeout_row["value"]) if timeout_row else 10

    cutoff = (now_utc() - timedelta(minutes=timeout_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stuck = conn.execute("""
        SELECT agent_id, agent_name, level, last_run_at
        FROM agents WHERE status = 'running' AND last_run_at < ?
    """, (cutoff,)).fetchall()
    report["stuck_agents"] = [dict(r) for r in stuck]

    # --- Failed sessions (last 24h) ---
    day_ago = (now_utc() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    failed_sessions = conn.execute("""
        SELECT session_id, agent_id, task_id, status, error_message, started_at
        FROM sessions WHERE status IN ('failed', 'timeout') AND started_at > ?
        ORDER BY started_at DESC LIMIT 20
    """, (day_ago,)).fetchall()
    report["failed_sessions_24h"] = [dict(r) for r in failed_sessions]

    # --- Skill registry stats ---
    skill_total = conn.execute(
        "SELECT COUNT(*) as cnt FROM skill_registry WHERE is_active = 1"
    ).fetchone()["cnt"]
    skill_stats = conn.execute("""
        SELECT SUM(success_count) as total_success, SUM(failure_count) as total_failure
        FROM skill_registry WHERE is_active = 1
    """).fetchone()
    report["skills"] = {
        "active_count": skill_total,
        "total_successes": skill_stats["total_success"] or 0,
        "total_failures": skill_stats["total_failure"] or 0,
    }

    # --- Memory stats ---
    long_count = conn.execute("SELECT COUNT(*) as cnt FROM memory_long").fetchone()["cnt"]
    short_count = conn.execute("SELECT COUNT(*) as cnt FROM memory_short").fetchone()["cnt"]
    top_categories = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM memory_long GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    report["memory"] = {
        "long_term_count": long_count,
        "short_term_count": short_count,
        "long_term_by_category": {r["category"]: r["cnt"] for r in top_categories},
    }

    # --- Cron schedules ---
    cron_total = conn.execute("SELECT COUNT(*) as cnt FROM cron_schedule").fetchone()["cnt"]
    cron_active = conn.execute(
        "SELECT COUNT(*) as cnt FROM cron_schedule WHERE is_enabled = 1"
    ).fetchone()["cnt"]
    report["cron_schedules"] = {
        "total": cron_total,
        "active": cron_active,
    }

    # --- Work releases ---
    release_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM work_releases GROUP BY status"
    ).fetchall()
    report["work_releases_by_status"] = {r["status"]: r["cnt"] for r in release_rows}

    # --- Improvement log ---
    improvement_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM improvement_log"
    ).fetchone()["cnt"]
    report["improvement_log_entries"] = improvement_count

    conn.close()
    return report


def print_report(report):
    """Print a human-readable health report."""
    print("=" * 60)
    print("  ULTRA AGENT SYSTEM — HEALTH REPORT")
    print("  Generated:", now_utc().strftime("%Y-%m-%d %H:%M:%S UTC"))
    print("=" * 60)

    print(f"\n--- Agents ({report['agents_total']} total) ---")
    for status, count in sorted(report["agents_by_status"].items()):
        marker = " (!)" if status == "error" else ""
        print(f"  {status:12s}: {count}{marker}")
    print("  By level:")
    for level, count in sorted(report["agents_by_level"].items()):
        print(f"    {level}: {count}")

    print(f"\n--- Tasks ({report['tasks_total']} total) ---")
    for status, count in sorted(report["tasks_by_status"].items()):
        print(f"  {status:20s}: {count}")

    stuck = report["stuck_agents"]
    if stuck:
        print(f"\n--- STUCK AGENTS ({len(stuck)}) ---")
        for a in stuck:
            print(f"  {a['agent_id']} ({a['agent_name']}) L{a['level']} — last run: {a['last_run_at']}")
    else:
        print("\n--- Stuck Agents: None ---")

    failed = report["failed_sessions_24h"]
    if failed:
        print(f"\n--- Failed Sessions (last 24h): {len(failed)} ---")
        for s in failed[:5]:
            print(f"  {s['session_id'][:8]}... agent={s['agent_id']} status={s['status']} at {s['started_at']}")
            if s.get("error_message"):
                print(f"    Error: {s['error_message'][:100]}")
    else:
        print("\n--- Failed Sessions (last 24h): None ---")

    skills = report["skills"]
    print(f"\n--- Skills ---")
    print(f"  Active: {skills['active_count']}")
    print(f"  Successes: {skills['total_successes']} | Failures: {skills['total_failures']}")

    mem = report["memory"]
    print(f"\n--- Memory ---")
    print(f"  Long-term: {mem['long_term_count']} | Short-term: {mem['short_term_count']}")
    if mem["long_term_by_category"]:
        for cat, cnt in mem["long_term_by_category"].items():
            print(f"    {cat}: {cnt}")

    cron = report["cron_schedules"]
    print(f"\n--- Cron Schedules ---")
    print(f"  Total: {cron['total']} | Active: {cron['active']}")

    releases = report.get("work_releases_by_status", {})
    print(f"\n--- Work Releases ---")
    for status, count in sorted(releases.items()):
        print(f"  {status:15s}: {count}")

    print(f"\n--- Improvement Log: {report['improvement_log_entries']} entries ---")
    print("=" * 60)


def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}", file=sys.stderr)
        print("Run 'python scripts/db-init.py' first.", file=sys.stderr)
        sys.exit(1)

    report = check_health()

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
