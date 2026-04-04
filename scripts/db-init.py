#!/usr/bin/env python3
"""Initialize the Ultra Agent SQLite database with all tables and seed data."""

import sqlite3
import uuid
import os
import sys
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ultra.db")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_tables(conn):
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL")

    c.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        agent_id        TEXT PRIMARY KEY,
        agent_name      TEXT NOT NULL,
        agent_type      TEXT NOT NULL CHECK(agent_type IN (
            'director','planner','librarian','researcher',
            'executor','auditor','improvement','sub_agent','worker'
        )),
        level           INTEGER NOT NULL CHECK(level BETWEEN 0 AND 3),
        parent_agent_id TEXT REFERENCES agents(agent_id),
        status          TEXT NOT NULL DEFAULT 'idle' CHECK(status IN ('idle','running','error','retired')),
        prompt_file     TEXT,
        skill_id        TEXT,
        sub_agent_role  TEXT CHECK(sub_agent_role IN ('tinker','planner','designer') OR sub_agent_role IS NULL),
        config_json     TEXT NOT NULL DEFAULT '{}',
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL,
        last_run_at     TEXT,
        run_count       INTEGER NOT NULL DEFAULT 0,
        error_count     INTEGER NOT NULL DEFAULT 0,
        session_id      TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id         TEXT PRIMARY KEY,
        parent_task_id  TEXT REFERENCES tasks(task_id),
        title           TEXT NOT NULL,
        description     TEXT,
        status          TEXT NOT NULL DEFAULT 'pending' CHECK(status IN (
            'pending','assigned','awaiting_release','in_progress',
            'blocked','review','completed','failed','cancelled'
        )),
        priority        INTEGER NOT NULL DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
        assigned_agent  TEXT REFERENCES agents(agent_id),
        created_by      TEXT REFERENCES agents(agent_id),
        framework       TEXT,
        toolkits_json   TEXT NOT NULL DEFAULT '[]',
        input_data      TEXT,
        output_data     TEXT,
        error_message   TEXT,
        depends_on_json TEXT NOT NULL DEFAULT '[]',
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL,
        started_at      TEXT,
        completed_at    TEXT,
        deadline        TEXT,
        retry_count     INTEGER NOT NULL DEFAULT 0,
        max_retries     INTEGER NOT NULL DEFAULT 3
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_agent)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id)")

    c.execute("""
    CREATE TABLE IF NOT EXISTS memory_long (
        memory_id    TEXT PRIMARY KEY,
        agent_id     TEXT NOT NULL,
        category     TEXT NOT NULL CHECK(category IN (
            'fact','preference','approach','domain_knowledge',
            'relationship','pattern','constraint'
        )),
        subject      TEXT NOT NULL,
        content      TEXT NOT NULL,
        confidence   REAL NOT NULL DEFAULT 1.0 CHECK(confidence BETWEEN 0.0 AND 1.0),
        source       TEXT,
        tags_json    TEXT NOT NULL DEFAULT '[]',
        access_count INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL,
        expires_at   TEXT
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_memory_long_agent ON memory_long(agent_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_memory_long_category ON memory_long(category)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_memory_long_subject ON memory_long(subject)")

    c.execute("""
    CREATE TABLE IF NOT EXISTS memory_short (
        memory_id  TEXT PRIMARY KEY,
        task_id    TEXT NOT NULL REFERENCES tasks(task_id),
        agent_id   TEXT NOT NULL REFERENCES agents(agent_id),
        key        TEXT NOT NULL,
        value      TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(task_id, agent_id, key)
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_memory_short_task ON memory_short(task_id)")

    c.execute("""
    CREATE TABLE IF NOT EXISTS skill_registry (
        skill_id       TEXT PRIMARY KEY,
        skill_name     TEXT NOT NULL,
        namespace      TEXT NOT NULL,
        category       TEXT NOT NULL,
        description    TEXT NOT NULL,
        agent_template TEXT NOT NULL,
        data_schema    TEXT NOT NULL DEFAULT '{}',
        output_schema  TEXT NOT NULL DEFAULT '{}',
        tools_required TEXT NOT NULL DEFAULT '[]',
        success_count  INTEGER NOT NULL DEFAULT 0,
        failure_count  INTEGER NOT NULL DEFAULT 0,
        version        INTEGER NOT NULL DEFAULT 1,
        is_active      INTEGER NOT NULL DEFAULT 1,
        last_used_at   TEXT,
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL,
        UNIQUE(namespace, skill_name)
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_skill_name ON skill_registry(skill_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_skill_namespace ON skill_registry(namespace)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_skill_category ON skill_registry(category)")

    c.execute("""
    CREATE TABLE IF NOT EXISTS skill_invocations (
        invocation_id    TEXT PRIMARY KEY,
        skill_id         TEXT NOT NULL REFERENCES skill_registry(skill_id),
        task_id          TEXT NOT NULL REFERENCES tasks(task_id),
        agent_id         TEXT NOT NULL REFERENCES agents(agent_id),
        input_data       TEXT NOT NULL,
        output_data      TEXT,
        status           TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','completed','failed')),
        duration_seconds REAL,
        error_message    TEXT,
        created_at       TEXT NOT NULL,
        completed_at     TEXT
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_invocations_skill ON skill_invocations(skill_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_invocations_task ON skill_invocations(task_id)")

    c.execute("""
    CREATE TABLE IF NOT EXISTS cron_schedule (
        schedule_id     TEXT PRIMARY KEY,
        agent_id        TEXT NOT NULL REFERENCES agents(agent_id),
        cron_expression TEXT NOT NULL,
        task_template   TEXT,
        is_enabled      INTEGER NOT NULL DEFAULT 1,
        last_fired_at   TEXT,
        next_fire_at    TEXT,
        fire_count      INTEGER NOT NULL DEFAULT 0,
        max_fires       INTEGER,
        created_at      TEXT NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS events (
        event_id   TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        agent_id   TEXT REFERENCES agents(agent_id),
        task_id    TEXT REFERENCES tasks(task_id),
        data_json  TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at)")

    c.execute("""
    CREATE TABLE IF NOT EXISTS work_releases (
        release_id           TEXT PRIMARY KEY,
        task_id              TEXT NOT NULL REFERENCES tasks(task_id),
        agent_id             TEXT NOT NULL REFERENCES agents(agent_id),
        agent_level          INTEGER NOT NULL CHECK(agent_level BETWEEN 0 AND 3),
        title                TEXT NOT NULL,
        description          TEXT,
        action_type          TEXT NOT NULL CHECK(action_type IN (
            'plan','research','design','execute','review','store'
        )),
        input_preview        TEXT,
        output_preview       TEXT,
        status               TEXT NOT NULL DEFAULT 'pending' CHECK(status IN (
            'pending','approved','rejected','auto_released'
        )),
        auto_release         INTEGER NOT NULL DEFAULT 0,
        auto_release_rule_id TEXT REFERENCES auto_release_rules(rule_id),
        reviewed_at          TEXT,
        created_at           TEXT NOT NULL
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_releases_status ON work_releases(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_releases_task ON work_releases(task_id)")

    c.execute("""
    CREATE TABLE IF NOT EXISTS auto_release_rules (
        rule_id                 TEXT PRIMARY KEY,
        match_agent_type        TEXT NOT NULL DEFAULT '*',
        match_action_type       TEXT NOT NULL DEFAULT '*',
        match_skill_id          TEXT,
        match_title_pattern     TEXT,
        is_enabled              INTEGER NOT NULL DEFAULT 1,
        created_from_release_id TEXT,
        fire_count              INTEGER NOT NULL DEFAULT 0,
        created_at              TEXT NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS improvement_log (
        log_id       TEXT PRIMARY KEY,
        task_id      TEXT REFERENCES tasks(task_id),
        agent_id     TEXT REFERENCES agents(agent_id),
        category     TEXT NOT NULL CHECK(category IN (
            'success_pattern','failure_pattern','approach_rating',
            'toolkit_feedback','skill_refinement','process_suggestion'
        )),
        summary      TEXT NOT NULL,
        details      TEXT,
        impact_score REAL CHECK(impact_score BETWEEN -1.0 AND 1.0),
        action_taken TEXT,
        created_at   TEXT NOT NULL
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_improvement_category ON improvement_log(category)")

    c.execute("""
    CREATE TABLE IF NOT EXISTS config (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    conn.commit()


def seed_agents(conn):
    """Insert the Director and 6 Level-1 agents."""
    c = conn.cursor()
    ts = now_iso()

    agents = [
        ("director",    "Director",    "director",    0, None, "agents/director.md"),
        ("planner",     "Planner",     "planner",     1, "director", "agents/planner.md"),
        ("librarian",   "Librarian",   "librarian",   1, "director", "agents/librarian.md"),
        ("researcher",  "Researcher",  "researcher",  1, "director", "agents/researcher.md"),
        ("executor",    "Executor",    "executor",    1, "director", "agents/executor.md"),
        ("auditor",     "Auditor",     "auditor",     1, "director", "agents/auditor.md"),
        ("improvement", "Improvement", "improvement", 1, "director", "agents/improvement.md"),
    ]

    for agent_id, name, atype, level, parent, prompt in agents:
        c.execute("""
            INSERT OR IGNORE INTO agents (agent_id, agent_name, agent_type, level, parent_agent_id, prompt_file, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (agent_id, name, atype, level, parent, prompt, ts, ts))

    defaults = [
        ("default_namespace", "jfchong.alliedgroup"),
        ("max_concurrent_agents", "5"),
        ("max_instances_per_type", "2"),
        ("agent_cooldown_seconds", "30"),
        ("stuck_agent_timeout_minutes", "10"),
    ]
    for key, value in defaults:
        c.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (key, value))

    conn.commit()


def main():
    exists = os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)
    seed_agents(conn)
    conn.close()

    if exists:
        print(f"Database updated: {DB_PATH}")
    else:
        print(f"Database created: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print(f"Tables ({len(tables)}): {', '.join(t[0] for t in tables)}")
    agents = conn.execute("SELECT agent_id, agent_name, level FROM agents ORDER BY level, agent_name").fetchall()
    print(f"Agents ({len(agents)}):")
    for a in agents:
        print(f"  L{a[2]}: {a[0]} ({a[1]})")
    conn.close()


if __name__ == "__main__":
    main()
