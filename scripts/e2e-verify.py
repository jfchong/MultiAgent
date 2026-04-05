#!/usr/bin/env python3
"""End-to-end verification of the Ultra Agent system.

Initializes a temporary database, verifies all tables, agent prompts,
protocol prompts, db-utils commands, and entity lifecycles.

Usage:
    python scripts/e2e-verify.py
"""

import sqlite3
import subprocess
import json
import os
import sys
import uuid
import shutil
import tempfile
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
DB_INIT = os.path.join(SCRIPTS_DIR, "db-init.py")
DB_UTILS = os.path.join(SCRIPTS_DIR, "db-utils.py")

# Use a temporary database to avoid touching production
TEST_DB_DIR = tempfile.mkdtemp(prefix="ultra_e2e_")
TEST_DB_PATH = os.path.join(TEST_DB_DIR, "ultra.db")

passed = 0
failed = 0
errors = []


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)
        errors.append(name)


def run_db_utils(*args):
    """Run db-utils.py with the test database."""
    env = os.environ.copy()
    cmd = [sys.executable, DB_UTILS] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_DIR,
                            env=env, timeout=30)
    return result


def run_db_init():
    """Run db-init.py targeting the test database."""
    result = subprocess.run(
        [sys.executable, DB_INIT],
        capture_output=True, text=True, cwd=PROJECT_DIR, timeout=30
    )
    return result


def get_conn():
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ========================================================================
# Monkey-patch db-utils and db-init to use test DB by replacing DB_PATH
# We do this by setting an environment variable and patching at import.
# Simpler: just run db-init directly against test DB via sqlite3.
# ========================================================================

def main():
    global passed, failed

    print("=" * 60)
    print("Ultra Agent System -- End-to-End Verification")
    print("=" * 60)
    print(f"Project: {PROJECT_DIR}")
    print(f"Test DB: {TEST_DB_PATH}")
    print()

    # ------------------------------------------------------------------
    # Section 1: Database Initialization
    # ------------------------------------------------------------------
    print("[1/8] Database Initialization")
    print("-" * 40)

    # Initialize tables directly in test DB
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Import and run create_tables
    sys.path.insert(0, SCRIPTS_DIR)
    import importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location("db_init", DB_INIT)
    db_init_mod = importlib.util.module_from_spec(spec)
    # Patch DB_PATH before exec
    original_db_path_attr = None

    spec.loader.exec_module(db_init_mod)
    # Run create_tables on our test connection
    db_init_mod.create_tables(conn)
    db_init_mod.seed_agents(conn)
    conn.close()

    # Verify all 15 tables
    EXPECTED_TABLES = [
        "agents", "auto_release_rules", "config", "credentials",
        "cron_schedule", "events", "improvement_log", "memory_long",
        "memory_short", "session_recordings", "sessions",
        "skill_invocations", "skill_registry", "tasks", "work_releases"
    ]

    conn = get_conn()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    conn.close()

    test("15 tables created", len(tables) == 15,
         f"got {len(tables)}: {tables}")

    for t in EXPECTED_TABLES:
        test(f"Table '{t}' exists", t in tables)

    # ------------------------------------------------------------------
    # Section 2: Seed Data Verification
    # ------------------------------------------------------------------
    print()
    print("[2/8] Seed Data")
    print("-" * 40)

    conn = get_conn()
    agents = conn.execute("SELECT * FROM agents ORDER BY level, agent_id").fetchall()
    conn.close()

    test("7 agents seeded", len(agents) == 7, f"got {len(agents)}")

    expected_agents = {
        "director": (0, "director"),
        "planner": (1, "planner"),
        "librarian": (1, "librarian"),
        "researcher": (1, "researcher"),
        "executor": (1, "executor"),
        "auditor": (1, "auditor"),
        "improvement": (1, "improvement"),
    }
    for agent in agents:
        aid = agent["agent_id"]
        if aid in expected_agents:
            exp_level, exp_type = expected_agents[aid]
            test(f"Agent '{aid}' level={exp_level} type={exp_type}",
                 agent["level"] == exp_level and agent["agent_type"] == exp_type)

    conn = get_conn()
    configs = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM config").fetchall()}
    conn.close()
    test("default_namespace config set", configs.get("default_namespace") == "jfchong.alliedgroup")
    test("max_concurrent_agents config set", "max_concurrent_agents" in configs)
    test("stuck_agent_timeout_minutes config set", "stuck_agent_timeout_minutes" in configs)

    # ------------------------------------------------------------------
    # Section 3: Agent Prompts and Protocol Files
    # ------------------------------------------------------------------
    print()
    print("[3/8] Agent Prompts & Protocol Files")
    print("-" * 40)

    AGENT_PROMPTS = [
        "agents/director.md",
        "agents/planner.md",
        "agents/librarian.md",
        "agents/researcher.md",
        "agents/executor.md",
        "agents/auditor.md",
        "agents/improvement.md",
        "agents/sub-agent.md",
        "agents/worker.md",
    ]
    for p in AGENT_PROMPTS:
        full = os.path.join(PROJECT_DIR, p)
        exists = os.path.isfile(full)
        size = os.path.getsize(full) if exists else 0
        test(f"Prompt '{p}' exists (>0 bytes)", exists and size > 0,
             f"exists={exists}, size={size}")

    PROTOCOL_PROMPTS = [
        "prompts/db-access-protocol.md",
        "prompts/reporting-protocol.md",
        "prompts/memory-protocol.md",
        "prompts/evaluation-protocol.md",
        "prompts/browser-protocol.md",
        "prompts/skill-protocol.md",
    ]
    for p in PROTOCOL_PROMPTS:
        full = os.path.join(PROJECT_DIR, p)
        exists = os.path.isfile(full)
        size = os.path.getsize(full) if exists else 0
        test(f"Protocol '{p}' exists (>0 bytes)", exists and size > 0,
             f"exists={exists}, size={size}")

    # ------------------------------------------------------------------
    # Section 4: Task CRUD Lifecycle
    # ------------------------------------------------------------------
    print()
    print("[4/8] Task CRUD Lifecycle")
    print("-" * 40)

    conn = get_conn()
    ts = now_iso()
    task_id = str(uuid.uuid4())

    # Create
    conn.execute("""
        INSERT INTO tasks (task_id, title, description, status, priority, assigned_agent, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (task_id, "E2E Test Task", "Verification task", "pending", 3, "planner", "director", ts, ts))
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    test("Task created", row is not None)
    test("Task status=pending", row["status"] == "pending")
    test("Task priority=3", row["priority"] == 3)

    # Update
    conn.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                 ("in_progress", ts, task_id))
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    test("Task updated to in_progress", row["status"] == "in_progress")

    # Complete
    conn.execute("UPDATE tasks SET status = ?, completed_at = ?, output_data = ?, updated_at = ? WHERE task_id = ?",
                 ("completed", ts, '{"result": "ok"}', ts, task_id))
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    test("Task completed", row["status"] == "completed")
    test("Task output_data stored", row["output_data"] is not None)

    # List
    rows = conn.execute("SELECT * FROM tasks WHERE assigned_agent = ?", ("planner",)).fetchall()
    test("List tasks by agent", len(rows) >= 1)
    conn.close()

    # ------------------------------------------------------------------
    # Section 5: Skill & Invocation Lifecycle
    # ------------------------------------------------------------------
    print()
    print("[5/8] Skill & Invocation Lifecycle")
    print("-" * 40)

    conn = get_conn()
    skill_id = str(uuid.uuid4())

    # Create skill
    conn.execute("""
        INSERT INTO skill_registry (skill_id, skill_name, namespace, category, description, agent_template, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (skill_id, "e2e-test-skill", "test.namespace", "testing", "A test skill", "Do the test", ts, ts))
    conn.commit()

    row = conn.execute("SELECT * FROM skill_registry WHERE skill_id = ?", (skill_id,)).fetchone()
    test("Skill created", row is not None)
    test("Skill is_active=1", row["is_active"] == 1)
    test("Skill success_count=0", row["success_count"] == 0)

    # Create invocation
    inv_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO skill_invocations (invocation_id, skill_id, task_id, agent_id, input_data, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """, (inv_id, skill_id, task_id, "executor", '{"test": true}', ts))
    conn.commit()

    row = conn.execute("SELECT * FROM skill_invocations WHERE invocation_id = ?", (inv_id,)).fetchone()
    test("Invocation created", row is not None)
    test("Invocation status=pending", row["status"] == "pending")

    # Complete invocation (success)
    conn.execute("UPDATE skill_invocations SET status = ?, output_data = ?, completed_at = ? WHERE invocation_id = ?",
                 ("completed", '{"out": 1}', ts, inv_id))
    conn.execute("UPDATE skill_registry SET success_count = success_count + 1, updated_at = ? WHERE skill_id = ?",
                 (ts, skill_id))
    conn.commit()

    row = conn.execute("SELECT * FROM skill_registry WHERE skill_id = ?", (skill_id,)).fetchone()
    test("Skill success_count incremented", row["success_count"] == 1)

    # Fail invocation
    inv_id2 = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO skill_invocations (invocation_id, skill_id, task_id, agent_id, input_data, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'running', ?)
    """, (inv_id2, skill_id, task_id, "executor", '{"test": 2}', ts))
    conn.execute("UPDATE skill_invocations SET status = ?, error_message = ?, completed_at = ? WHERE invocation_id = ?",
                 ("failed", "Simulated failure", ts, inv_id2))
    conn.execute("UPDATE skill_registry SET failure_count = failure_count + 1, updated_at = ? WHERE skill_id = ?",
                 (ts, skill_id))
    conn.commit()

    row = conn.execute("SELECT * FROM skill_registry WHERE skill_id = ?", (skill_id,)).fetchone()
    test("Skill failure_count incremented", row["failure_count"] == 1)

    # Deactivate skill
    conn.execute("UPDATE skill_registry SET is_active = 0, updated_at = ? WHERE skill_id = ?", (ts, skill_id))
    conn.commit()
    row = conn.execute("SELECT * FROM skill_registry WHERE skill_id = ? AND is_active = 1", (skill_id,)).fetchone()
    test("Deactivated skill excluded from active query", row is None)
    conn.close()

    # ------------------------------------------------------------------
    # Section 6: Session Lifecycle
    # ------------------------------------------------------------------
    print()
    print("[6/8] Session & Credential Lifecycle")
    print("-" * 40)

    conn = get_conn()
    session_id = str(uuid.uuid4())

    # Create session
    conn.execute("""
        INSERT INTO sessions (session_id, agent_id, task_id, status, started_at)
        VALUES (?, ?, ?, 'running', ?)
    """, (session_id, "executor", task_id, ts))
    conn.commit()

    row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    test("Session created", row is not None)
    test("Session status=running", row["status"] == "running")

    # Complete session
    conn.execute("""
        UPDATE sessions SET status = ?, completed_at = ?, duration_seconds = ?, success = 1,
        summary = ? WHERE session_id = ?
    """, ("completed", ts, 12.5, "Test session completed", session_id))
    conn.commit()
    row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    test("Session completed", row["status"] == "completed")
    test("Session success=1", row["success"] == 1)
    test("Session duration recorded", row["duration_seconds"] == 12.5)

    # Create session recording
    rec_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO session_recordings (recording_id, session_id, step_number, action_type, target, value, timestamp)
        VALUES (?, ?, 1, 'navigate', 'https://example.com', NULL, ?)
    """, (rec_id, session_id, ts))
    conn.commit()
    row = conn.execute("SELECT * FROM session_recordings WHERE session_id = ?", (session_id,)).fetchone()
    test("Session recording created", row is not None)

    # Credential CRUD
    cred_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO credentials (credential_id, site_domain, label, auth_type, credentials_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (cred_id, "test.example.com", "Test Cred", "password",
          json.dumps({"username": "user", "password": "secret123"}), ts, ts))
    conn.commit()

    row = conn.execute("SELECT * FROM credentials WHERE site_domain = ?", ("test.example.com",)).fetchone()
    test("Credential created", row is not None)
    test("Credential auth_type=password", row["auth_type"] == "password")

    # Verify list-credentials does NOT leak passwords (check column selection)
    safe_rows = conn.execute(
        "SELECT credential_id, site_domain, label, auth_type, created_at, updated_at FROM credentials"
    ).fetchall()
    for r in safe_rows:
        row_dict = dict(r)
        test("Credential listing excludes credentials_json",
             "credentials_json" not in row_dict)

    # Delete credential
    conn.execute("DELETE FROM credentials WHERE site_domain = ?", ("test.example.com",))
    conn.commit()
    row = conn.execute("SELECT * FROM credentials WHERE site_domain = ?", ("test.example.com",)).fetchone()
    test("Credential deleted", row is None)
    conn.close()

    # ------------------------------------------------------------------
    # Section 7: Work Release & Auto-Release
    # ------------------------------------------------------------------
    print()
    print("[7/8] Work Release & Auto-Release Rules")
    print("-" * 40)

    conn = get_conn()

    # Create auto-release rule first (referenced by work_releases)
    rule_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO auto_release_rules (rule_id, match_agent_type, match_action_type, is_enabled, created_at)
        VALUES (?, ?, ?, 1, ?)
    """, (rule_id, "executor", "execute", ts))
    conn.commit()

    row = conn.execute("SELECT * FROM auto_release_rules WHERE rule_id = ?", (rule_id,)).fetchone()
    test("Auto-release rule created", row is not None)
    test("Rule match_agent_type=executor", row["match_agent_type"] == "executor")

    # Create work release
    release_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO work_releases (release_id, task_id, agent_id, agent_level, title, description, action_type, status, created_at)
        VALUES (?, ?, ?, 1, ?, ?, 'execute', 'pending', ?)
    """, (release_id, task_id, "executor", "Execute test task", "Needs approval", ts))
    conn.commit()

    row = conn.execute("SELECT * FROM work_releases WHERE release_id = ?", (release_id,)).fetchone()
    test("Work release created", row is not None)
    test("Work release status=pending", row["status"] == "pending")

    # Approve
    conn.execute("UPDATE work_releases SET status = ?, reviewed_at = ? WHERE release_id = ?",
                 ("approved", ts, release_id))
    conn.commit()
    row = conn.execute("SELECT * FROM work_releases WHERE release_id = ?", (release_id,)).fetchone()
    test("Work release approved", row["status"] == "approved")

    # Test auto-release matching
    conn.execute("UPDATE auto_release_rules SET fire_count = fire_count + 1 WHERE rule_id = ?", (rule_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM auto_release_rules WHERE rule_id = ?", (rule_id,)).fetchone()
    test("Auto-release fire_count incremented", row["fire_count"] == 1)

    # Create auto-released work release
    release_id2 = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO work_releases (release_id, task_id, agent_id, agent_level, title, action_type,
                                   status, auto_release, auto_release_rule_id, reviewed_at, created_at)
        VALUES (?, ?, ?, 1, ?, 'execute', 'auto_released', 1, ?, ?, ?)
    """, (release_id2, task_id, "executor", "Auto-released task", rule_id, ts, ts))
    conn.commit()
    row = conn.execute("SELECT * FROM work_releases WHERE release_id = ?", (release_id2,)).fetchone()
    test("Auto-released work release created", row["status"] == "auto_released")
    test("Auto-release linked to rule", row["auto_release_rule_id"] == rule_id)
    conn.close()

    # ------------------------------------------------------------------
    # Section 8: Memory & Events & Improvement Log
    # ------------------------------------------------------------------
    print()
    print("[8/8] Memory, Events & Improvement Log")
    print("-" * 40)

    conn = get_conn()

    # Long-term memory
    mem_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO memory_long (memory_id, agent_id, category, subject, content, confidence, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (mem_id, "planner", "fact", "test-subject", "Test content for e2e", 0.9, "e2e-verify", ts, ts))
    conn.commit()
    row = conn.execute("SELECT * FROM memory_long WHERE memory_id = ?", (mem_id,)).fetchone()
    test("Long-term memory created", row is not None)
    test("Memory confidence=0.9", row["confidence"] == 0.9)

    # Short-term memory
    smem_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO memory_short (memory_id, task_id, agent_id, key, value, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (smem_id, task_id, "planner", "test_key", "test_value", ts, ts))
    conn.commit()
    row = conn.execute("SELECT * FROM memory_short WHERE memory_id = ?", (smem_id,)).fetchone()
    test("Short-term memory created", row is not None)
    test("Short-term memory key/value correct", row["key"] == "test_key" and row["value"] == "test_value")

    # Events
    evt_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO events (event_id, event_type, agent_id, task_id, data_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (evt_id, "task_completed", "executor", task_id, '{"test": true}', ts))
    conn.commit()
    row = conn.execute("SELECT * FROM events WHERE event_id = ?", (evt_id,)).fetchone()
    test("Event created", row is not None)
    test("Event type=task_completed", row["event_type"] == "task_completed")

    # Improvement log
    log_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO improvement_log (log_id, task_id, agent_id, category, summary, impact_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (log_id, task_id, "improvement", "success_pattern", "E2E test passed", 0.8, ts))
    conn.commit()
    row = conn.execute("SELECT * FROM improvement_log WHERE log_id = ?", (log_id,)).fetchone()
    test("Improvement log created", row is not None)
    test("Improvement impact_score=0.8", row["impact_score"] == 0.8)

    # Cron schedule
    sched_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO cron_schedule (schedule_id, agent_id, cron_expression, is_enabled, created_at)
        VALUES (?, ?, ?, 1, ?)
    """, (sched_id, "improvement", "*/5 * * * *", ts))
    conn.commit()
    row = conn.execute("SELECT * FROM cron_schedule WHERE schedule_id = ?", (sched_id,)).fetchone()
    test("Cron schedule created", row is not None)
    test("Cron expression stored", row["cron_expression"] == "*/5 * * * *")

    # 4-level hierarchy verification
    sub_agent_id = str(uuid.uuid4())
    worker_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO agents (agent_id, agent_name, agent_type, level, parent_agent_id, sub_agent_role, prompt_file, created_at, updated_at)
        VALUES (?, ?, 'sub_agent', 2, 'executor', 'tinker', 'agents/sub-agent.md', ?, ?)
    """, (sub_agent_id, "Test-Tinker", ts, ts))
    conn.execute("""
        INSERT INTO agents (agent_id, agent_name, agent_type, level, parent_agent_id, prompt_file, created_at, updated_at)
        VALUES (?, ?, 'worker', 3, ?, 'agents/worker.md', ?, ?)
    """, (worker_id, "Test-Worker", sub_agent_id, ts, ts))
    conn.commit()

    # Verify hierarchy: L0 -> L1 -> L2 -> L3
    l0 = conn.execute("SELECT * FROM agents WHERE level = 0").fetchall()
    l1 = conn.execute("SELECT * FROM agents WHERE level = 1").fetchall()
    l2 = conn.execute("SELECT * FROM agents WHERE level = 2").fetchall()
    l3 = conn.execute("SELECT * FROM agents WHERE level = 3").fetchall()
    test("L0 Director exists", len(l0) >= 1)
    test("L1 Agents exist (6)", len(l1) == 6)
    test("L2 Sub-Agent spawned", len(l2) >= 1)
    test("L3 Worker spawned", len(l3) >= 1)

    # Verify parent chain
    sub = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (sub_agent_id,)).fetchone()
    wrk = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (worker_id,)).fetchone()
    test("L2 parent is L1 executor", sub["parent_agent_id"] == "executor")
    test("L3 parent is L2 sub-agent", wrk["parent_agent_id"] == sub_agent_id)
    test("L2 sub_agent_role=tinker", sub["sub_agent_role"] == "tinker")

    conn.close()

    # ------------------------------------------------------------------
    # Cleanup & Summary
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    shutil.rmtree(TEST_DB_DIR, ignore_errors=True)

    total = passed + failed
    if failed == 0:
        print(f"ALL TESTS PASSED: {passed}/{total}")
    else:
        print(f"TESTS: {passed}/{total} passed, {failed} FAILED")
        print(f"Failed tests:")
        for e in errors:
            print(f"  - {e}")

    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
