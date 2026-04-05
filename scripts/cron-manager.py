#!/usr/bin/env python3
"""Cron Manager — Autonomous tick-loop scheduler for the Ultra Agent system.

Runs a 1-minute tick cycle that:
1. Checks cron_schedule for due jobs -> creates tasks
2. Checks work_releases for pending items -> applies auto_release_rules
3. Checks approved releases -> moves tasks to in_progress
4. Dispatches ready tasks in parallel via dispatch-agent.sh
5. Resolves blocked tasks whose dependencies completed
6. Health-checks for stuck agents (>10 min)

Usage:
  python scripts/cron-manager.py              # Run tick loop
  python scripts/cron-manager.py --once       # Run a single tick and exit
  python scripts/cron-manager.py --dry-run    # Show what would happen without acting
"""

import sqlite3
import subprocess
import json
import uuid
import os
import sys
import time
import logging
import signal
from datetime import datetime, timezone, timedelta

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, "ultra.db")
DISPATCH_SCRIPT = os.path.join(PROJECT_DIR, "scripts", "dispatch-agent.sh")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")

# Ensure logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "cron-manager.log")),
    ],
)
log = logging.getLogger("cron-manager")

# Track running agent processes: {pid: {"agent_id": ..., "task_id": ..., "started_at": ...}}
RUNNING_PROCESSES = {}

# Graceful shutdown flag
SHUTDOWN = False


def signal_handler(signum, frame):
    global SHUTDOWN
    log.info("Received signal %d, shutting down after current tick...", signum)
    SHUTDOWN = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_utc():
    return datetime.now(timezone.utc)


def enable_wal_mode(db_path):
    """Enable WAL mode for concurrent read/write access."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()
    log.info("WAL mode enabled for %s", db_path)


def get_conn():
    """Get a connection with WAL mode and row_factory."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_config(conn, key, default=None):
    """Read a config value from the config table."""
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_max_concurrent(conn):
    return int(get_config(conn, "max_concurrent_agents", "5"))


def get_stuck_timeout(conn):
    return int(get_config(conn, "stuck_agent_timeout_minutes", "10"))


def cron_matches_now(cron_expression, dt=None):
    """Check if a 5-field cron expression matches the given datetime.

    Supports: * (any), integers, comma-separated values, ranges (e.g., 1-5),
    and step values (e.g., */5).

    Fields: minute hour day_of_month month day_of_week
    Day of week: 0=Monday ... 6=Sunday (ISO convention)
    """
    if dt is None:
        dt = now_utc()

    fields = cron_expression.strip().split()
    if len(fields) != 5:
        log.warning("Invalid cron expression (need 5 fields): %s", cron_expression)
        return False

    values = [dt.minute, dt.hour, dt.day, dt.month, dt.weekday()]
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]

    for field, actual, (lo, hi) in zip(fields, values, ranges):
        if not _field_matches(field, actual, lo, hi):
            return False
    return True


def _field_matches(field, actual, lo, hi):
    """Check if a single cron field matches the actual value."""
    for part in field.split(","):
        # Handle step: */5 or 1-10/2
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            if base == "*":
                if actual % step == 0:
                    return True
            elif "-" in base:
                start, end = map(int, base.split("-", 1))
                if start <= actual <= end and (actual - start) % step == 0:
                    return True
        elif part == "*":
            return True
        elif "-" in part:
            start, end = map(int, part.split("-", 1))
            if start <= actual <= end:
                return True
        else:
            if int(part) == actual:
                return True
    return False


def check_cron_jobs(conn, dry_run=False):
    """Check cron_schedule for due jobs and create tasks."""
    rows = conn.execute(
        "SELECT * FROM cron_schedule WHERE is_enabled = 1"
    ).fetchall()

    created = 0
    now = now_utc()

    for row in rows:
        schedule_id = row["schedule_id"]
        cron_expr = row["cron_expression"]
        agent_id = row["agent_id"]
        template = row["task_template"]
        max_fires = row["max_fires"]
        fire_count = row["fire_count"]

        # Check max fires limit
        if max_fires is not None and fire_count >= max_fires:
            log.debug("Schedule %s reached max fires (%d), skipping", schedule_id, max_fires)
            continue

        # Check if cron expression matches current minute
        if not cron_matches_now(cron_expr, now):
            continue

        # Check if already fired this minute (prevent double-fire)
        last_fired = row["last_fired_at"]
        if last_fired:
            try:
                last_dt = datetime.fromisoformat(last_fired.replace("Z", "+00:00"))
                if (now - last_dt).total_seconds() < 60:
                    continue
            except ValueError:
                pass

        if dry_run:
            log.info("[DRY RUN] Would create task from schedule %s for agent %s", schedule_id, agent_id)
            continue

        # Parse task template
        try:
            tmpl = json.loads(template) if template else {}
        except json.JSONDecodeError:
            log.warning("Invalid task_template JSON for schedule %s", schedule_id)
            continue

        task_id = str(uuid.uuid4())
        ts = now_iso()
        title = tmpl.get("title", f"Scheduled task for {agent_id}")
        description = tmpl.get("description", f"Auto-created by cron schedule {schedule_id}")
        priority = tmpl.get("priority", 5)
        framework = tmpl.get("framework")
        input_data = tmpl.get("input_data")

        conn.execute("""
            INSERT INTO tasks (task_id, title, description, status, priority, assigned_agent,
                               created_by, framework, input_data, created_at, updated_at)
            VALUES (?, ?, ?, 'assigned', ?, ?, 'cron_manager', ?, ?, ?, ?)
        """, (task_id, title, description, priority, agent_id, framework, input_data, ts, ts))

        conn.execute("""
            UPDATE cron_schedule SET last_fired_at = ?, fire_count = fire_count + 1, next_fire_at = NULL
            WHERE schedule_id = ?
        """, (ts, schedule_id))

        # Log event
        conn.execute("""
            INSERT INTO events (event_id, event_type, agent_id, task_id, data_json, created_at)
            VALUES (?, 'cron_fired', ?, ?, ?, ?)
        """, (str(uuid.uuid4()), agent_id, task_id, json.dumps({"schedule_id": schedule_id}), ts))

        conn.commit()
        created += 1
        log.info("Created task %s from schedule %s for agent %s", task_id, schedule_id, agent_id)

    return created


def check_auto_releases(conn, dry_run=False):
    """Check pending work_releases and auto-approve those matching auto_release_rules."""
    pending = conn.execute(
        "SELECT * FROM work_releases WHERE status = 'pending'"
    ).fetchall()

    if not pending:
        return 0

    rules = conn.execute(
        "SELECT * FROM auto_release_rules WHERE is_enabled = 1"
    ).fetchall()

    if not rules:
        return 0

    approved = 0
    ts = now_iso()

    for release in pending:
        release_id = release["release_id"]
        agent_id = release["agent_id"]
        action_type = release["action_type"]
        title = release["title"]

        # Look up agent type
        agent_row = conn.execute(
            "SELECT agent_type FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        agent_type = agent_row["agent_type"] if agent_row else None

        for rule in rules:
            # Match agent_type
            if rule["match_agent_type"] != "*" and rule["match_agent_type"] != agent_type:
                continue
            # Match action_type
            if rule["match_action_type"] != "*" and rule["match_action_type"] != action_type:
                continue
            # Match title pattern (simple LIKE)
            if rule["match_title_pattern"]:
                pattern = rule["match_title_pattern"]
                if pattern.replace("%", "").lower() not in title.lower():
                    continue

            if dry_run:
                log.info("[DRY RUN] Would auto-release %s (rule %s)", release_id, rule["rule_id"])
                break

            conn.execute("""
                UPDATE work_releases SET status = 'auto_released', auto_release = 1,
                       auto_release_rule_id = ?, reviewed_at = ?
                WHERE release_id = ?
            """, (rule["rule_id"], ts, release_id))

            conn.execute("""
                UPDATE auto_release_rules SET fire_count = fire_count + 1
                WHERE rule_id = ?
            """, (rule["rule_id"],))

            conn.execute("""
                INSERT INTO events (event_id, event_type, agent_id, task_id, data_json, created_at)
                VALUES (?, 'auto_released', ?, ?, ?, ?)
            """, (str(uuid.uuid4()), agent_id, release["task_id"],
                  json.dumps({"release_id": release_id, "rule_id": rule["rule_id"]}), ts))

            conn.commit()
            approved += 1
            log.info("Auto-released %s via rule %s", release_id, rule["rule_id"])
            break  # Only one rule needs to match

    return approved


def check_approved_releases(conn, dry_run=False):
    """Move tasks from awaiting_release to in_progress when their release is approved."""
    rows = conn.execute("""
        SELECT wr.release_id, wr.task_id, wr.agent_id
        FROM work_releases wr
        JOIN tasks t ON wr.task_id = t.task_id
        WHERE wr.status IN ('approved', 'auto_released')
          AND t.status = 'awaiting_release'
    """).fetchall()

    moved = 0
    ts = now_iso()

    for row in rows:
        if dry_run:
            log.info("[DRY RUN] Would move task %s to in_progress", row["task_id"])
            continue

        conn.execute("""
            UPDATE tasks SET status = 'in_progress', updated_at = ?
            WHERE task_id = ? AND status = 'awaiting_release'
        """, (ts, row["task_id"]))

        conn.commit()
        moved += 1
        log.info("Moved task %s to in_progress (release %s approved)", row["task_id"], row["release_id"])

    return moved


def reap_finished_processes():
    """Check for finished subprocesses and clean up."""
    finished = []
    for pid, info in RUNNING_PROCESSES.items():
        proc = info["proc"]
        retcode = proc.poll()
        if retcode is not None:
            finished.append(pid)
            duration = (now_utc() - info["started_at"]).total_seconds()
            if retcode == 0:
                log.info("Agent %s (task %s, PID %d) completed in %.1fs",
                         info["agent_id"], info["task_id"], pid, duration)
            else:
                log.warning("Agent %s (task %s, PID %d) exited with code %d after %.1fs",
                            info["agent_id"], info["task_id"], pid, retcode, duration)
                # Mark agent as error
                try:
                    conn = get_conn()
                    ts = now_iso()
                    conn.execute(
                        "UPDATE agents SET status = 'error', updated_at = ? WHERE agent_id = ?",
                        (ts, info["agent_id"])
                    )
                    conn.execute(
                        "UPDATE tasks SET status = 'failed', error_message = ?, updated_at = ? WHERE task_id = ? AND status = 'in_progress'",
                        (f"Agent exited with code {retcode}", ts, info["task_id"])
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    log.error("Failed to update status for crashed agent: %s", e)

    for pid in finished:
        del RUNNING_PROCESSES[pid]


def dispatch_ready_tasks(conn, dry_run=False):
    """Find tasks ready for dispatch and launch agents in parallel."""
    reap_finished_processes()

    max_concurrent = get_max_concurrent(conn)
    current_running = len(RUNNING_PROCESSES)

    if current_running >= max_concurrent:
        log.debug("At concurrency limit (%d/%d), skipping dispatch", current_running, max_concurrent)
        return 0

    slots = max_concurrent - current_running

    # Find tasks that are assigned or in_progress but not yet dispatched
    # Exclude tasks whose agents are already running in our process table
    running_agent_ids = {info["agent_id"] for info in RUNNING_PROCESSES.values()}
    running_task_ids = {info["task_id"] for info in RUNNING_PROCESSES.values()}

    rows = conn.execute("""
        SELECT t.task_id, t.assigned_agent, t.priority
        FROM tasks t
        JOIN agents a ON t.assigned_agent = a.agent_id
        WHERE t.status IN ('assigned', 'in_progress')
          AND a.status IN ('idle', 'error')
        ORDER BY t.priority ASC, t.created_at ASC
    """).fetchall()

    dispatched = 0

    for row in rows:
        if dispatched >= slots:
            break

        task_id = row["task_id"]
        agent_id = row["assigned_agent"]

        # Skip if this task is already being dispatched
        if task_id in running_task_ids:
            continue

        # Skip if this specific agent instance is already running
        # (but allow multiple instances of same agent_type via different agent_ids)
        if agent_id in running_agent_ids:
            continue

        if dry_run:
            log.info("[DRY RUN] Would dispatch agent %s for task %s", agent_id, task_id)
            dispatched += 1
            continue

        # Dispatch via subprocess
        cmd = ["bash", DISPATCH_SCRIPT, agent_id, task_id, "sonnet", "--background"]
        log.info("Dispatching: %s", " ".join(cmd))

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=PROJECT_DIR,
            )
            RUNNING_PROCESSES[proc.pid] = {
                "proc": proc,
                "agent_id": agent_id,
                "task_id": task_id,
                "started_at": now_utc(),
            }
            running_agent_ids.add(agent_id)
            running_task_ids.add(task_id)
            dispatched += 1
            log.info("Dispatched agent %s for task %s (PID %d) [%d/%d slots used]",
                     agent_id, task_id, proc.pid, len(RUNNING_PROCESSES), max_concurrent)
        except Exception as e:
            log.error("Failed to dispatch agent %s for task %s: %s", agent_id, task_id, e)

    return dispatched


def check_blocked_tasks(conn, dry_run=False):
    """Check blocked tasks whose dependencies are all completed and unblock them."""
    rows = conn.execute(
        "SELECT task_id, depends_on_json, assigned_agent FROM tasks WHERE status = 'blocked'"
    ).fetchall()

    unblocked = 0
    ts = now_iso()

    for row in rows:
        task_id = row["task_id"]
        try:
            deps = json.loads(row["depends_on_json"])
        except (json.JSONDecodeError, TypeError):
            deps = []

        if not deps:
            # No dependencies listed but status is blocked — unblock it
            if not dry_run:
                conn.execute(
                    "UPDATE tasks SET status = 'assigned', updated_at = ? WHERE task_id = ?",
                    (ts, task_id)
                )
                conn.commit()
            unblocked += 1
            log.info("Unblocked task %s (no dependencies)", task_id)
            continue

        # Check if all dependencies are completed
        placeholders = ",".join("?" for _ in deps)
        completed = conn.execute(
            f"SELECT COUNT(*) as cnt FROM tasks WHERE task_id IN ({placeholders}) AND status = 'completed'",
            deps
        ).fetchone()["cnt"]

        failed = conn.execute(
            f"SELECT COUNT(*) as cnt FROM tasks WHERE task_id IN ({placeholders}) AND status IN ('failed', 'cancelled')",
            deps
        ).fetchone()["cnt"]

        if failed > 0:
            # If any dependency failed, mark this task as failed too
            if not dry_run:
                conn.execute(
                    "UPDATE tasks SET status = 'failed', error_message = 'Dependency failed', updated_at = ? WHERE task_id = ?",
                    (ts, task_id)
                )
                conn.commit()
            log.warning("Task %s failed due to dependency failure", task_id)
            continue

        if completed == len(deps):
            if dry_run:
                log.info("[DRY RUN] Would unblock task %s (all %d deps completed)", task_id, len(deps))
            else:
                conn.execute(
                    "UPDATE tasks SET status = 'assigned', updated_at = ? WHERE task_id = ?",
                    (ts, task_id)
                )
                conn.commit()
            unblocked += 1
            log.info("Unblocked task %s (all %d dependencies completed)", task_id, len(deps))

    return unblocked


def health_check(conn, dry_run=False):
    """Detect agents stuck in 'running' state for longer than the configured timeout."""
    timeout_minutes = get_stuck_timeout(conn)
    cutoff = (now_utc() - timedelta(minutes=timeout_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

    stuck = conn.execute("""
        SELECT agent_id, agent_name, last_run_at, session_id
        FROM agents
        WHERE status = 'running' AND last_run_at < ?
    """, (cutoff,)).fetchall()

    fixed = 0
    ts = now_iso()

    for agent in stuck:
        agent_id = agent["agent_id"]
        log.warning("Agent %s (%s) stuck since %s (>%d min)",
                     agent_id, agent["agent_name"], agent["last_run_at"], timeout_minutes)

        if dry_run:
            continue

        # Mark agent as error
        conn.execute(
            "UPDATE agents SET status = 'error', updated_at = ? WHERE agent_id = ?",
            (ts, agent_id)
        )

        # Fail any in_progress tasks for this agent
        conn.execute("""
            UPDATE tasks SET status = 'failed', error_message = 'Agent stuck timeout',
                   updated_at = ?
            WHERE assigned_agent = ? AND status = 'in_progress'
        """, (ts, agent_id))

        # Update session if tracked
        conn.execute("""
            UPDATE sessions SET status = 'timeout', completed_at = ?
            WHERE agent_id = ? AND status = 'running'
        """, (ts, agent_id))

        # Log event
        conn.execute("""
            INSERT INTO events (event_id, event_type, agent_id, data_json, created_at)
            VALUES (?, 'agent_stuck', ?, ?, ?)
        """, (str(uuid.uuid4()), agent_id,
              json.dumps({"last_run_at": agent["last_run_at"], "timeout_minutes": timeout_minutes}), ts))

        conn.commit()
        fixed += 1
        log.info("Marked stuck agent %s as error and failed its tasks", agent_id)

    # Also clean up RUNNING_PROCESSES for PIDs that no longer exist
    orphans = []
    for pid, info in RUNNING_PROCESSES.items():
        proc = info["proc"]
        if proc.poll() is not None:
            orphans.append(pid)
    for pid in orphans:
        del RUNNING_PROCESSES[pid]

    return fixed


def tick(dry_run=False):
    """Execute one scheduling cycle."""
    tick_start = time.time()
    log.info("=== TICK START === [%d agents running]", len(RUNNING_PROCESSES))

    try:
        conn = get_conn()

        # Phase 1: Create tasks from cron schedules
        cron_created = check_cron_jobs(conn, dry_run)

        # Phase 2: Auto-release matching work releases
        auto_released = check_auto_releases(conn, dry_run)

        # Phase 3: Move approved releases to in_progress
        releases_moved = check_approved_releases(conn, dry_run)

        # Phase 4: Resolve blocked task dependencies
        unblocked = check_blocked_tasks(conn, dry_run)

        # Phase 5: Dispatch ready tasks
        dispatched = dispatch_ready_tasks(conn, dry_run)

        # Phase 6: Health check for stuck agents
        stuck_fixed = health_check(conn, dry_run)

        conn.close()

        elapsed = time.time() - tick_start
        log.info(
            "=== TICK END === (%.2fs) cron=%d auto_release=%d released=%d unblocked=%d dispatched=%d stuck=%d running=%d",
            elapsed, cron_created, auto_released, releases_moved, unblocked, dispatched, stuck_fixed,
            len(RUNNING_PROCESSES),
        )
    except Exception as e:
        log.error("Tick failed: %s", e, exc_info=True)


def main():
    """Run the cron manager loop."""
    dry_run = "--dry-run" in sys.argv
    once = "--once" in sys.argv

    if dry_run:
        log.info("Running in DRY RUN mode — no changes will be made")

    enable_wal_mode(DB_PATH)
    log.info("Cron Manager starting (PID %d, project=%s)", os.getpid(), PROJECT_DIR)
    log.info("Config: max_concurrent=%s, stuck_timeout=%s min",
             get_config(get_conn(), "max_concurrent_agents", "5"),
             get_config(get_conn(), "stuck_agent_timeout_minutes", "10"))

    if once:
        log.info("Single tick mode (--once)")
        tick(dry_run)
        return

    log.info("Entering tick loop (60s interval). Ctrl+C to stop.")
    while not SHUTDOWN:
        tick(dry_run)
        # Sleep in 1-second increments to allow graceful shutdown
        for _ in range(60):
            if SHUTDOWN:
                break
            time.sleep(1)

    log.info("Cron Manager shutting down. Waiting for %d running agents...", len(RUNNING_PROCESSES))
    for pid, info in RUNNING_PROCESSES.items():
        log.info("  PID %d: agent=%s task=%s", pid, info["agent_id"], info["task_id"])
    log.info("Cron Manager stopped.")


if __name__ == "__main__":
    main()
