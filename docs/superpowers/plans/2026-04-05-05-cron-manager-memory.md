# Phase 5: Cron Manager & Memory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the autonomous Cron Manager that wakes agents with pending work on a 1-minute tick cycle with parallel dispatch, implement a standalone health-check script, and add agent management commands to db-utils. Together these form the autonomous scheduling backbone that lets the Ultra Agent system run unattended.

**Architecture:** The Cron Manager (`cron-manager.py`) runs as a long-lived Python process with a 60-second tick loop. Each tick checks five sources of work: cron schedules, auto-release rules, approved releases, ready tasks, and blocked tasks with resolved dependencies. It dispatches agents in parallel via `subprocess.Popen` calling `dispatch-agent.sh`, tracks PIDs, enforces a configurable concurrency limit (default 5), and detects stuck agents. A separate `health-check.py` provides on-demand system status. Three new db-utils commands (`list-agents`, `create-agent`, `update-agent`) complete the agent lifecycle management needed for Sub-Agent/Worker spawning.

**Tech Stack:** Python 3 (sqlite3, subprocess, threading, time, json, logging), Bash, SQLite WAL mode

---

## File Map

| File | Responsibility |
|------|---------------|
| `scripts/cron-manager.py` | Autonomous tick-loop scheduler: cron jobs, auto-release, dispatch, health check |
| `scripts/health-check.py` | Standalone on-demand system health report |
| `scripts/db-utils.py` | Add commands: list-agents, create-agent, update-agent (18 -> 21 total) |
| `scripts/db-init.py` | Already has WAL mode (verified), no changes needed |

---

### Task 1: Build Cron Manager

**Files:**
- Create: `scripts/cron-manager.py`

- [ ] **Step 1: Create the cron-manager.py file with all imports and constants**

```python
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
```

- [ ] **Step 2: Add `enable_wal_mode` and `get_config` helpers**

```python
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
```

- [ ] **Step 3: Add `cron_matches_now` helper for cron expression parsing**

This is a minimal cron parser supporting standard 5-field expressions (minute, hour, day-of-month, month, day-of-week) with `*` and integer values. No external dependencies.

```python
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
```

- [ ] **Step 4: Add `check_cron_jobs` — create tasks from due cron schedules**

```python
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
```

- [ ] **Step 5: Add `check_auto_releases` — match pending releases against rules**

```python
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
```

- [ ] **Step 6: Add `check_approved_releases` — move approved tasks to in_progress**

```python
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
```

- [ ] **Step 7: Add `dispatch_ready_tasks` — find and dispatch tasks via subprocess**

```python
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
```

- [ ] **Step 8: Add `check_blocked_tasks` — resolve dependencies**

```python
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
```

- [ ] **Step 9: Add `health_check` — detect stuck agents**

```python
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
```

- [ ] **Step 10: Add `tick` and `main` functions**

```python
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
```

- [ ] **Step 11: Verify the script runs without errors**

```bash
cd C:/Users/jfcho/Desktop/CoWork/MultiAgent
python scripts/cron-manager.py --once --dry-run
```

Expected output: tick logs showing no errors, zero actions taken (no cron schedules or pending tasks in empty DB).

- [ ] **Step 12: Commit**

```bash
git add scripts/cron-manager.py
git commit -m "feat: add cron-manager.py — autonomous tick-loop scheduler with parallel dispatch

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Build Health Check Script

**Files:**
- Create: `scripts/health-check.py`

- [ ] **Step 1: Create the health-check.py file**

```python
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
```

- [ ] **Step 2: Verify the script runs**

```bash
cd C:/Users/jfcho/Desktop/CoWork/MultiAgent
python scripts/health-check.py
python scripts/health-check.py --json
```

- [ ] **Step 3: Commit**

```bash
git add scripts/health-check.py
git commit -m "feat: add health-check.py — on-demand system health report

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Add Agent Management Commands to db-utils.py

**Files:**
- Modify: `scripts/db-utils.py`

These three commands complete the agent lifecycle management needed for the Cron Manager and for L1 agents to spawn Sub-Agents and Workers at runtime.

- [ ] **Step 1: Add `cmd_list_agents` function**

Add before the `COMMANDS` dict:

```python
def cmd_list_agents(args):
    """List agents with optional --status, --level, --type filters."""
    conditions = []
    params = []
    i = 0
    while i < len(args):
        if args[i] == "--status":
            conditions.append("status = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--level":
            conditions.append("level = ?")
            params.append(int(args[i + 1]))
            i += 2
        elif args[i] == "--type":
            conditions.append("agent_type = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--parent":
            conditions.append("parent_agent_id = ?")
            params.append(args[i + 1])
            i += 2
        else:
            i += 1

    sql = "SELECT * FROM agents"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY level ASC, agent_name ASC"

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))
```

- [ ] **Step 2: Add `cmd_create_agent` function**

```python
def cmd_create_agent(args):
    """Create a new agent (for Sub-Agent/Worker spawning).

    Usage:
      python db-utils.py create-agent --name "Tinker-ABC" --type sub_agent --level 2 --parent executor
        [--prompt-file agents/sub-agent.md] [--sub-role tinker] [--config '{"key":"val"}']
    """
    name = agent_type = prompt_file = sub_role = None
    level = None
    parent = None
    config_json = "{}"
    i = 0
    while i < len(args):
        if args[i] == "--name":
            name = args[i + 1]; i += 2
        elif args[i] == "--type":
            agent_type = args[i + 1]; i += 2
        elif args[i] == "--level":
            level = int(args[i + 1]); i += 2
        elif args[i] == "--parent":
            parent = args[i + 1]; i += 2
        elif args[i] == "--prompt-file":
            prompt_file = args[i + 1]; i += 2
        elif args[i] == "--sub-role":
            sub_role = args[i + 1]; i += 2
        elif args[i] == "--config":
            config_json = args[i + 1]; i += 2
        else:
            i += 1

    if not name or not agent_type or level is None:
        print("Error: --name, --type, and --level are required", file=sys.stderr)
        sys.exit(1)

    agent_id = f"{agent_type[:4]}-{uuid.uuid4().hex[:8]}"
    ts = now_iso()

    conn = get_conn()
    conn.execute("""
        INSERT INTO agents (agent_id, agent_name, agent_type, level, parent_agent_id,
                            prompt_file, sub_agent_role, config_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (agent_id, name, agent_type, level, parent, prompt_file, sub_role, config_json, ts, ts))
    conn.commit()
    conn.close()

    print(json.dumps({"agent_id": agent_id, "agent_name": name, "agent_type": agent_type, "level": level}))
```

- [ ] **Step 3: Add `cmd_update_agent` function**

```python
def cmd_update_agent(args):
    """Update agent fields.

    Usage:
      python db-utils.py update-agent <agent_id> --status idle --config '{"key":"val"}'
    """
    agent_id = args[0]
    updates = {}
    i = 1
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:].replace("-", "_")
            # Map common aliases
            if key == "prompt_file":
                key = "prompt_file"
            elif key == "sub_role":
                key = "sub_agent_role"
            elif key == "config":
                key = "config_json"
            updates[key] = args[i + 1]
            i += 2
        else:
            i += 1

    if not updates:
        print("Error: no updates specified", file=sys.stderr)
        sys.exit(1)

    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [agent_id]

    conn = get_conn()
    conn.execute(f"UPDATE agents SET {set_clause} WHERE agent_id = ?", params)
    conn.commit()
    conn.close()
    print(json.dumps({"agent_id": agent_id, "updated": list(updates.keys())}))
```

- [ ] **Step 4: Register all three commands in the COMMANDS dict**

Update the `COMMANDS` dict to add the three new entries:

```python
COMMANDS = {
    "query": cmd_query,
    "get-agent": cmd_get_agent,
    "list-agents": cmd_list_agents,         # NEW
    "create-agent": cmd_create_agent,       # NEW
    "update-agent": cmd_update_agent,       # NEW
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
```

- [ ] **Step 5: Verify all commands work**

```bash
cd C:/Users/jfcho/Desktop/CoWork/MultiAgent
python scripts/db-utils.py list-agents
python scripts/db-utils.py list-agents --level 1
python scripts/db-utils.py list-agents --status idle
python scripts/db-utils.py create-agent --name "Test-Tinker" --type sub_agent --level 2 --parent executor --sub-role tinker --prompt-file agents/sub-agent.md
python scripts/db-utils.py list-agents --level 2
python scripts/db-utils.py update-agent <agent_id_from_above> --status running
python scripts/db-utils.py update-agent <agent_id_from_above> --status retired
```

- [ ] **Step 6: Commit**

```bash
git add scripts/db-utils.py
git commit -m "feat: add list-agents, create-agent, update-agent commands to db-utils (18 -> 21)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Integration Verification

**Files:**
- No new files; verification only

- [ ] **Step 1: Reinitialize the database to ensure clean state**

```bash
cd C:/Users/jfcho/Desktop/CoWork/MultiAgent
rm -f ultra.db
python scripts/db-init.py
```

Verify output shows 15 tables and 7 agents.

- [ ] **Step 2: Verify WAL mode is active**

```bash
python -c "
import sqlite3
db = sqlite3.connect('C:/Users/jfcho/Desktop/CoWork/MultiAgent/ultra.db')
mode = db.execute('PRAGMA journal_mode').fetchone()[0]
print(f'Journal mode: {mode}')
assert mode == 'wal', f'Expected wal, got {mode}'
print('WAL mode verified.')
db.close()
"
```

- [ ] **Step 3: Create a test cron schedule and verify tick picks it up**

```bash
cd C:/Users/jfcho/Desktop/CoWork/MultiAgent

# Create a cron schedule that fires every minute
python -c "
import sqlite3, json, uuid
from datetime import datetime, timezone
db = sqlite3.connect('ultra.db')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('''INSERT INTO cron_schedule (schedule_id, agent_id, cron_expression, task_template, is_enabled, created_at)
    VALUES (?, ?, ?, ?, 1, ?)''',
    (str(uuid.uuid4()), 'improvement', '* * * * *',
     json.dumps({'title': 'Periodic improvement scan', 'description': 'Auto-scheduled improvement analysis', 'priority': 7}),
     ts))
db.commit()
db.close()
print('Cron schedule created.')
"

# Run one tick in dry-run mode
python scripts/cron-manager.py --once --dry-run
```

Expected: log line showing "[DRY RUN] Would create task from schedule ... for agent improvement"

- [ ] **Step 4: Run one real tick and verify task creation**

```bash
cd C:/Users/jfcho/Desktop/CoWork/MultiAgent
python scripts/cron-manager.py --once
python scripts/db-utils.py list-tasks --agent improvement
```

Expected: one task with status "assigned" and title "Periodic improvement scan".

- [ ] **Step 5: Run the health check**

```bash
python scripts/health-check.py
python scripts/health-check.py --json
```

Expected: report showing 7 agents (all idle), 1 task (assigned), 1 cron schedule (active).

- [ ] **Step 6: Verify db-utils command count is 21**

```bash
python -c "
import sys
sys.argv = ['db-utils.py']
# Just count the COMMANDS dict
exec(open('C:/Users/jfcho/Desktop/CoWork/MultiAgent/scripts/db-utils.py').read().split('if __name__')[0])
print(f'Total commands: {len(COMMANDS)}')
assert len(COMMANDS) == 21, f'Expected 21 commands, got {len(COMMANDS)}'
print('Command count verified.')
"
```

- [ ] **Step 7: Clean up test data and re-initialize**

```bash
cd C:/Users/jfcho/Desktop/CoWork/MultiAgent
rm -f ultra.db
python scripts/db-init.py
```

- [ ] **Step 8: Final commit (if any fixups were needed)**

```bash
git add -A
git status
# Only commit if there are changes
git diff --cached --quiet || git commit -m "fix: integration fixes for Phase 5 cron manager and memory system

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Summary

| Task | Files | Commands Added | Key Capability |
|------|-------|---------------|----------------|
| 1 | `scripts/cron-manager.py` (create) | N/A | Autonomous 60s tick loop: cron, auto-release, dispatch, health |
| 2 | `scripts/health-check.py` (create) | N/A | On-demand system health report (text + JSON) |
| 3 | `scripts/db-utils.py` (modify) | list-agents, create-agent, update-agent | Agent lifecycle management (18 -> 21 commands) |
| 4 | Verification only | N/A | End-to-end integration test of tick cycle |

**After Phase 5, the system has:**
- Autonomous scheduling via `python scripts/cron-manager.py`
- Parallel agent dispatch with configurable concurrency (max 5)
- Auto-release gate integration
- Stuck agent detection and recovery
- On-demand health monitoring
- Full agent CRUD for dynamic Sub-Agent/Worker spawning
- 21 db-utils commands total
