# Ultra Agent Monitoring Dashboard — Design Specification

**Date:** 2026-04-05
**Status:** Approved
**Author:** JF Chong + Claude
**Dependencies:** Ultra Agent Design Spec, Browser Sessions Design Spec

---

## 1. Architecture

### Overview

A React single-page application (SPA) that provides a comprehensive monitoring and management interface for the Ultra Agent multi-agent orchestration platform. The dashboard replaces the existing vanilla HTML/CSS/JS Work Release UI with a full-featured command center.

### Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript |
| Build | Vite 5 |
| UI Components | Shadcn/ui (Radix primitives) |
| Styling | Tailwind CSS 3 (dark theme) |
| State/Fetching | React hooks + 5-second polling |
| Backend | Python 3.11+ HTTP server (stdlib `http.server`) |
| Database | SQLite 3 (WAL mode) |
| Browser Automation | Playwright (Python) |

### Deployment Model

```
User Browser (React SPA)
    |  HTTP/JSON on port 53800
    v
dashboard-server.py (Python, single process)
    |  Serves: static files (React build) + JSON API
    v
ultra.db (SQLite, WAL mode)
    |  Shared with:
    v
cron-manager.py / dispatch-agent.sh / claude -p agents
```

- **Development:** Vite dev server on port 5173 proxies `/api/*` to `dashboard-server.py` on port 53800.
- **Production:** `dashboard-server.py` serves the `dashboard/dist/` build output as static files and handles all `/api/*` routes directly. Single port, single process.
- **Database access:** All reads and writes go through `dashboard-server.py`. The server opens SQLite connections per-request with WAL mode to avoid blocking the cron manager and agent processes that also access `ultra.db`.

### Server Replacement Strategy

The new `scripts/dashboard-server.py` fully replaces `scripts/release-server.py`:

1. All existing release API endpoints are preserved with identical request/response shapes (backward compatible).
2. New endpoints are added for every dashboard feature.
3. Static file serving switches from `ui/` to `dashboard/dist/`.
4. `startup.bat` is updated to launch `dashboard-server.py` instead of `release-server.py`.
5. Port remains 53800.

---

## 2. API Endpoints

All endpoints return JSON. Error responses use the shape `{"error": "message"}` with appropriate HTTP status codes. CORS headers are included on all responses.

### 2.1 System

#### `GET /api/status`

KPI metrics for the overview page.

**Response:**
```json
{
  "running_agents": 2,
  "pending_tasks": 5,
  "pending_releases": 3,
  "completed_today": 12,
  "success_rate": 0.87,
  "total_agents": 7,
  "total_tasks": 48,
  "tasks_by_status": {
    "pending": 5,
    "assigned": 2,
    "awaiting_release": 3,
    "in_progress": 4,
    "completed": 30,
    "failed": 4
  }
}
```

**SQL:** Aggregates from `agents`, `tasks`, `work_releases`. `completed_today` filters `tasks.completed_at` to current UTC date. `success_rate` = completed / (completed + failed) for all time.

#### `GET /api/activity?limit=50`

Recent activity feed combining events, task completions, and session completions.

**Query params:**
- `limit` (int, default 50) — max items to return

**Response:**
```json
[
  {
    "id": "evt-abc123",
    "type": "event",
    "event_type": "task_assigned",
    "agent_id": "executor",
    "agent_name": "Executor",
    "task_id": "task-xyz",
    "task_title": "Implement login flow",
    "summary": "Executor assigned to task",
    "timestamp": "2026-04-05T10:30:00Z",
    "data": {}
  }
]
```

**SQL:** UNION query across `events`, `tasks` (where `completed_at` or `started_at` is recent), and `sessions` (where `completed_at` is recent). Ordered by timestamp descending, limited.

#### `GET /api/pipeline`

Task counts by status for pipeline visualization.

**Response:**
```json
{
  "pending": 5,
  "assigned": 2,
  "awaiting_release": 3,
  "in_progress": 4,
  "blocked": 0,
  "review": 1,
  "completed": 30,
  "failed": 4,
  "cancelled": 0
}
```

**SQL:** `SELECT status, COUNT(*) FROM tasks GROUP BY status`

---

### 2.2 Requests

#### `POST /api/requests`

Submit a new user request. Creates a top-level task and dispatches the Director.

**Request body:**
```json
{
  "title": "Build a login page for the admin portal",
  "description": "Full description of what the user wants...",
  "priority": 7
}
```

**Response:**
```json
{
  "ok": true,
  "task_id": "task-abc123",
  "status": "pending"
}
```

**Backend logic:**
1. Insert into `tasks` with `created_by='user'`, `status='pending'`.
2. Insert event `request_submitted`.
3. Optionally trigger Director dispatch via `dispatch-agent.sh director <task_id>`.

#### `GET /api/requests?limit=50&offset=0`

List user-submitted requests.

**Query params:**
- `limit` (int, default 50)
- `offset` (int, default 0)

**Response:**
```json
{
  "items": [
    {
      "task_id": "task-abc123",
      "title": "Build a login page",
      "description": "...",
      "status": "in_progress",
      "priority": 7,
      "created_at": "2026-04-05T09:00:00Z",
      "completed_at": null,
      "output_data": null,
      "subtask_count": 3,
      "completed_subtask_count": 1
    }
  ],
  "total": 15
}
```

**SQL:** `SELECT * FROM tasks WHERE created_by='user' ORDER BY created_at DESC`

---

### 2.3 Tasks

#### `GET /api/tasks`

List tasks with filters.

**Query params:**
- `status` (string, comma-separated, e.g. `pending,in_progress`)
- `agent` (string, agent_id)
- `priority_min` (int)
- `priority_max` (int)
- `parent_task_id` (string, for subtask queries)
- `search` (string, title LIKE search)
- `limit` (int, default 100)
- `offset` (int, default 0)

**Response:**
```json
{
  "items": [
    {
      "task_id": "task-abc",
      "parent_task_id": null,
      "title": "Build login page",
      "status": "in_progress",
      "priority": 7,
      "assigned_agent": "executor",
      "agent_name": "Executor",
      "created_by": "user",
      "framework": "systematic_decomposition",
      "created_at": "2026-04-05T09:00:00Z",
      "started_at": "2026-04-05T09:01:00Z",
      "completed_at": null,
      "duration_seconds": null
    }
  ],
  "total": 48
}
```

#### `GET /api/tasks/:id`

Full task detail including timeline events and subtask tree.

**Response:**
```json
{
  "task_id": "task-abc",
  "parent_task_id": null,
  "title": "Build login page",
  "description": "...",
  "status": "in_progress",
  "priority": 7,
  "assigned_agent": "executor",
  "agent_name": "Executor",
  "created_by": "user",
  "framework": "systematic_decomposition",
  "toolkits_json": "[\"quality-gate\", \"constraint-compliance\"]",
  "input_data": "{...}",
  "output_data": null,
  "error_message": null,
  "depends_on_json": "[]",
  "created_at": "2026-04-05T09:00:00Z",
  "updated_at": "2026-04-05T10:30:00Z",
  "started_at": "2026-04-05T09:01:00Z",
  "completed_at": null,
  "deadline": null,
  "retry_count": 0,
  "max_retries": 3,
  "timeline": [ "...see /api/tasks/:id/timeline..." ],
  "subtasks": [ "...see /api/tasks/:id/subtasks..." ]
}
```

#### `GET /api/tasks/:id/timeline`

Chronological events for a task — who did what and when.

**Response:**
```json
[
  {
    "event_id": "evt-001",
    "event_type": "task_created",
    "agent_id": null,
    "agent_name": null,
    "data": {},
    "timestamp": "2026-04-05T09:00:00Z"
  },
  {
    "event_id": "evt-002",
    "event_type": "task_assigned",
    "agent_id": "director",
    "agent_name": "Director",
    "data": {"assigned_to": "planner"},
    "timestamp": "2026-04-05T09:00:05Z"
  },
  {
    "event_id": "evt-003",
    "event_type": "subtask_created",
    "agent_id": "planner",
    "agent_name": "Planner",
    "data": {"subtask_id": "task-sub1", "title": "Design schema"},
    "timestamp": "2026-04-05T09:01:00Z"
  }
]
```

**SQL:** `SELECT * FROM events WHERE task_id = ? ORDER BY created_at ASC`, joined with `agents` for agent_name.

#### `GET /api/tasks/:id/subtasks`

Recursive subtask tree.

**Response:**
```json
[
  {
    "task_id": "task-sub1",
    "title": "Design schema",
    "status": "completed",
    "assigned_agent": "planner",
    "agent_name": "Planner",
    "priority": 7,
    "created_at": "2026-04-05T09:01:00Z",
    "completed_at": "2026-04-05T09:15:00Z",
    "children": [
      {
        "task_id": "task-sub1a",
        "title": "Research existing schemas",
        "status": "completed",
        "assigned_agent": "researcher",
        "agent_name": "Researcher",
        "priority": 7,
        "created_at": "2026-04-05T09:02:00Z",
        "completed_at": "2026-04-05T09:10:00Z",
        "children": []
      }
    ]
  }
]
```

**Backend logic:** Recursive CTE query on `tasks.parent_task_id`, then assembled into a tree in Python.

---

### 2.4 Agents

#### `GET /api/agents`

All agents with status, level, and counts.

**Response:**
```json
[
  {
    "agent_id": "director",
    "agent_name": "Director",
    "agent_type": "director",
    "level": 0,
    "parent_agent_id": null,
    "status": "idle",
    "run_count": 15,
    "error_count": 1,
    "success_rate": 0.93,
    "last_run_at": "2026-04-05T10:00:00Z",
    "active_task_count": 0
  }
]
```

**SQL:** Join `agents` with `COUNT` from `tasks` where `assigned_agent = agent_id AND status IN ('assigned','in_progress')`.

#### `GET /api/agents/:id`

Agent detail with task history.

**Response:**
```json
{
  "agent_id": "executor",
  "agent_name": "Executor",
  "agent_type": "executor",
  "level": 1,
  "parent_agent_id": "director",
  "status": "running",
  "prompt_file": "agents/executor.md",
  "config_json": "{}",
  "run_count": 42,
  "error_count": 3,
  "success_rate": 0.93,
  "last_run_at": "2026-04-05T10:30:00Z",
  "current_task": {
    "task_id": "task-xyz",
    "title": "Implement login flow",
    "status": "in_progress"
  },
  "recent_tasks": [
    {
      "task_id": "task-abc",
      "title": "Build header component",
      "status": "completed",
      "started_at": "2026-04-05T08:00:00Z",
      "completed_at": "2026-04-05T08:30:00Z"
    }
  ]
}
```

#### `GET /api/agents/:id/sessions`

Agent's session history.

**Query params:**
- `limit` (int, default 20)
- `offset` (int, default 0)

**Response:**
```json
{
  "items": [
    {
      "session_id": "sess-001",
      "task_id": "task-abc",
      "task_title": "Build header component",
      "browser_category": null,
      "status": "completed",
      "success": 1,
      "started_at": "2026-04-05T08:00:00Z",
      "completed_at": "2026-04-05T08:30:00Z",
      "duration_seconds": 1800.0,
      "summary": "Successfully built header component"
    }
  ],
  "total": 42
}
```

#### `GET /api/agents/hierarchy`

Tree structure for the agent hierarchy visualization.

**Response:**
```json
{
  "agent_id": "director",
  "agent_name": "Director",
  "agent_type": "director",
  "level": 0,
  "status": "idle",
  "run_count": 15,
  "error_count": 1,
  "children": [
    {
      "agent_id": "planner",
      "agent_name": "Planner",
      "agent_type": "planner",
      "level": 1,
      "status": "idle",
      "run_count": 30,
      "error_count": 2,
      "children": [
        {
          "agent_id": "sub-planner-001",
          "agent_name": "Planner Sub-Agent",
          "agent_type": "sub_agent",
          "level": 2,
          "status": "running",
          "run_count": 5,
          "error_count": 0,
          "children": []
        }
      ]
    }
  ]
}
```

**Backend logic:** Fetch all agents, build tree from `parent_agent_id` relationships. Root is the Director (level 0).

---

### 2.5 Releases

These endpoints are backward-compatible with the existing `release-server.py` API.

#### `GET /api/releases?status=pending`

List releases with optional status filter.

**Query params:**
- `status` (string: `pending`, `approved`, `rejected`, `auto_released`)

**Response:** Array of release objects with joined agent and task details (same shape as existing API).

#### `POST /api/releases/:id/approve`

Approve a pending release. Sets `work_releases.status = 'approved'` and advances `tasks.status` from `awaiting_release` to `in_progress`.

**Response:** `{"ok": true, "release_id": "...", "status": "approved"}`

#### `POST /api/releases/:id/reject`

Reject a pending release.

**Request body:**
```json
{
  "reason": "Optional rejection reason"
}
```

**Response:** `{"ok": true, "release_id": "...", "status": "rejected"}`

#### `POST /api/releases/:id/auto-release`

Approve a release and create an auto-release rule from it.

**Request body (optional overrides):**
```json
{
  "match_agent_type": "executor",
  "match_action_type": "execute",
  "match_skill_id": null,
  "match_title_pattern": null
}
```

**Response:** `{"ok": true, "release_id": "...", "status": "auto_released", "rule_id": "..."}`

#### `GET /api/rules`

List all auto-release rules.

**Response:** Array of `auto_release_rules` rows.

#### `DELETE /api/rules/:id`

Delete an auto-release rule.

**Response:** `{"ok": true, "rule_id": "...", "deleted": true}`

---

### 2.6 Skills

#### `GET /api/skills?search=login&category=browser`

List skills with search and filter.

**Query params:**
- `search` (string, matches `skill_name` or `description`)
- `category` (string)
- `namespace` (string)
- `active_only` (bool, default true)
- `limit` (int, default 100)
- `offset` (int, default 0)

**Response:**
```json
{
  "items": [
    {
      "skill_id": "skill-001",
      "skill_name": "css_login",
      "namespace": "jfchong.alliedgroup",
      "category": "browser",
      "description": "Log in to CSS Strata portal",
      "success_count": 45,
      "failure_count": 2,
      "success_rate": 0.96,
      "version": 3,
      "is_active": 1,
      "last_used_at": "2026-04-05T10:00:00Z",
      "created_at": "2026-03-15T08:00:00Z"
    }
  ],
  "total": 12
}
```

#### `GET /api/skills/:id`

Full skill detail with template.

**Response:**
```json
{
  "skill_id": "skill-001",
  "skill_name": "css_login",
  "namespace": "jfchong.alliedgroup",
  "category": "browser",
  "description": "Log in to CSS Strata portal",
  "agent_template": "...full skill template text...",
  "data_schema": {"unit_number": "string", "owner_name": "string"},
  "output_schema": {"balance": "number", "statement_url": "string"},
  "tools_required": ["browser"],
  "success_count": 45,
  "failure_count": 2,
  "version": 3,
  "is_active": 1,
  "last_used_at": "2026-04-05T10:00:00Z",
  "created_at": "2026-03-15T08:00:00Z",
  "updated_at": "2026-04-05T10:00:00Z"
}
```

#### `GET /api/skills/:id/invocations?limit=20`

Invocation history for a skill.

**Response:**
```json
{
  "items": [
    {
      "invocation_id": "inv-001",
      "task_id": "task-abc",
      "agent_id": "worker-001",
      "input_data": "{\"unit_number\": \"A-12-3\"}",
      "output_data": "{\"balance\": 150.00}",
      "status": "completed",
      "duration_seconds": 12.5,
      "error_message": null,
      "created_at": "2026-04-05T10:00:00Z",
      "completed_at": "2026-04-05T10:00:12Z"
    }
  ],
  "total": 45
}
```

#### `POST /api/skills/:id/test`

Test-run a skill with Playwright browser automation.

**Request body:**
```json
{
  "input_data": {
    "unit_number": "A-12-3",
    "owner_name": "Test Owner"
  },
  "headless": true
}
```

**Response (synchronous, blocks until completion):**
```json
{
  "ok": true,
  "skill_id": "skill-001",
  "status": "completed",
  "duration_seconds": 15.2,
  "steps": [
    {
      "step_number": 1,
      "action_type": "auto_login",
      "target": "csshome.info",
      "result": "success",
      "duration_ms": 3200
    },
    {
      "step_number": 2,
      "action_type": "navigate",
      "target": "https://csshome.info/accounts",
      "result": "success",
      "duration_ms": 1500
    },
    {
      "step_number": 3,
      "action_type": "fill",
      "target": "#unit-number",
      "value": "A-12-3",
      "result": "success",
      "duration_ms": 200
    },
    {
      "step_number": 4,
      "action_type": "click",
      "target": "#search-btn",
      "result": "success",
      "duration_ms": 800
    },
    {
      "step_number": 5,
      "action_type": "extract",
      "target": ".balance-amount",
      "result": "150.00",
      "duration_ms": 100
    }
  ],
  "output_data": {"balance": 150.00},
  "screenshot_path": "logs/screenshots/skill-001-test-20260405T100000.png"
}
```

**Backend logic:**
1. Load skill template from `skill_registry`.
2. Spawn `scripts/browser-runner.py` as subprocess with skill template JSON + input data as arguments.
3. Wait for subprocess to complete (timeout: 120 seconds).
4. Parse stdout JSON result.
5. Return to frontend.

**Timeout:** 120 seconds. If exceeded, returns `{"ok": false, "error": "Test run timed out after 120 seconds"}`.

---

### 2.7 Sessions

#### `GET /api/sessions`

List sessions with filters.

**Query params:**
- `agent` (string, agent_id)
- `status` (string: `running`, `completed`, `failed`, `timeout`)
- `browser_category` (string: `SS-SM`, `SS-MM`, `MS-SM`, `MS-MM`)
- `success` (bool)
- `limit` (int, default 50)
- `offset` (int, default 0)

**Response:**
```json
{
  "items": [
    {
      "session_id": "sess-001",
      "agent_id": "worker-001",
      "agent_name": "CSS Login Worker",
      "task_id": "task-abc",
      "task_title": "Check account balance",
      "browser_category": "SS-SM",
      "status": "completed",
      "success": 1,
      "started_at": "2026-04-05T10:00:00Z",
      "completed_at": "2026-04-05T10:00:15Z",
      "duration_seconds": 15.0,
      "summary": "Successfully logged in and extracted balance"
    }
  ],
  "total": 120
}
```

#### `GET /api/sessions/:id`

Session detail with recordings.

**Response:**
```json
{
  "session_id": "sess-001",
  "agent_id": "worker-001",
  "agent_name": "CSS Login Worker",
  "task_id": "task-abc",
  "task_title": "Check account balance",
  "parent_session_id": "sess-parent",
  "browser_category": "SS-SM",
  "status": "completed",
  "success": 1,
  "started_at": "2026-04-05T10:00:00Z",
  "completed_at": "2026-04-05T10:00:15Z",
  "duration_seconds": 15.0,
  "summary": "Successfully logged in and extracted balance",
  "output_snapshot": "{...}",
  "error_message": null,
  "recordings": [ "...see /api/sessions/:id/recordings..." ]
}
```

#### `GET /api/sessions/:id/recordings`

Step-by-step action log for a session.

**Response:**
```json
[
  {
    "recording_id": "rec-001",
    "step_number": 1,
    "action_type": "auto_login",
    "target": "csshome.info",
    "value": null,
    "result": "success",
    "timestamp": "2026-04-05T10:00:01Z",
    "duration_ms": 3200
  },
  {
    "recording_id": "rec-002",
    "step_number": 2,
    "action_type": "navigate",
    "target": "https://csshome.info/accounts",
    "value": null,
    "result": "success",
    "timestamp": "2026-04-05T10:00:04Z",
    "duration_ms": 1500
  }
]
```

**SQL:** `SELECT * FROM session_recordings WHERE session_id = ? ORDER BY step_number ASC`

---

### 2.8 Improvements

#### `GET /api/improvements`

List improvement log entries.

**Query params:**
- `category` (string: `success_pattern`, `failure_pattern`, `approach_rating`, `toolkit_feedback`, `skill_refinement`, `process_suggestion`)
- `agent` (string, agent_id)
- `limit` (int, default 50)
- `offset` (int, default 0)

**Response:**
```json
{
  "items": [
    {
      "log_id": "imp-001",
      "task_id": "task-abc",
      "task_title": "Build login page",
      "agent_id": "improvement",
      "agent_name": "Improvement",
      "category": "success_pattern",
      "summary": "Decomposition into 3 subtasks with parallel execution improved throughput by 40%",
      "details": "...",
      "impact_score": 0.8,
      "action_taken": "Updated planner prompt to prefer parallel decomposition",
      "created_at": "2026-04-05T11:00:00Z"
    }
  ],
  "total": 35
}
```

#### `GET /api/improvements/stats`

Aggregated improvement metrics.

**Response:**
```json
{
  "total_patterns": 35,
  "avg_impact_score": 0.42,
  "by_category": {
    "success_pattern": {"count": 12, "avg_impact": 0.65},
    "failure_pattern": {"count": 8, "avg_impact": -0.45},
    "approach_rating": {"count": 5, "avg_impact": 0.30},
    "toolkit_feedback": {"count": 4, "avg_impact": 0.20},
    "skill_refinement": {"count": 3, "avg_impact": 0.50},
    "process_suggestion": {"count": 3, "avg_impact": 0.35}
  },
  "top_improving_agents": [
    {"agent_id": "improvement", "agent_name": "Improvement", "count": 20, "avg_impact": 0.55}
  ]
}
```

---

### 2.9 Settings

#### `GET /api/config`

All config key-value pairs.

**Response:**
```json
[
  {"key": "default_namespace", "value": "jfchong.alliedgroup"},
  {"key": "max_concurrent_agents", "value": "5"},
  {"key": "max_instances_per_type", "value": "2"},
  {"key": "agent_cooldown_seconds", "value": "30"},
  {"key": "stuck_agent_timeout_minutes", "value": "10"}
]
```

#### `PUT /api/config/:key`

Update a config value.

**Request body:**
```json
{
  "value": "new_value"
}
```

**Response:** `{"ok": true, "key": "...", "value": "..."}`

**Backend logic:** `INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)`

#### `GET /api/credentials`

List credentials (never exposes passwords or credential JSON content).

**Response:**
```json
[
  {
    "credential_id": "cred-001",
    "site_domain": "csshome.info",
    "label": "CSS Strata Portal",
    "auth_type": "password",
    "created_at": "2026-03-15T08:00:00Z",
    "updated_at": "2026-04-01T12:00:00Z"
  }
]
```

**SQL:** `SELECT credential_id, site_domain, label, auth_type, created_at, updated_at FROM credentials` (explicitly excludes `credentials_json`).

#### `POST /api/credentials`

Add a new credential.

**Request body:**
```json
{
  "site_domain": "example.com",
  "label": "Example Portal",
  "auth_type": "password",
  "credentials_json": {"username": "user@example.com", "password": "secret"}
}
```

**Response:** `{"ok": true, "credential_id": "..."}`

#### `DELETE /api/credentials/:id`

Delete a credential.

**Response:** `{"ok": true, "credential_id": "...", "deleted": true}`

#### `GET /api/cron`

List all cron schedules.

**Response:**
```json
[
  {
    "schedule_id": "cron-001",
    "agent_id": "improvement",
    "agent_name": "Improvement",
    "cron_expression": "0 */6 * * *",
    "task_template": "{\"title\": \"6-hour activity summary\"}",
    "is_enabled": 1,
    "last_fired_at": "2026-04-05T06:00:00Z",
    "next_fire_at": "2026-04-05T12:00:00Z",
    "fire_count": 28,
    "max_fires": null,
    "created_at": "2026-03-20T08:00:00Z"
  }
]
```

#### `POST /api/cron`

Create a new cron schedule.

**Request body:**
```json
{
  "agent_id": "researcher",
  "cron_expression": "0 9 * * 1-5",
  "task_template": "{\"title\": \"Morning research digest\"}",
  "is_enabled": true,
  "max_fires": null
}
```

**Response:** `{"ok": true, "schedule_id": "..."}`

#### `PUT /api/cron/:id`

Update a cron schedule.

**Request body (partial updates allowed):**
```json
{
  "is_enabled": false
}
```

**Response:** `{"ok": true, "schedule_id": "..."}`

#### `DELETE /api/cron/:id`

Delete a cron schedule.

**Response:** `{"ok": true, "schedule_id": "...", "deleted": true}`

---

## 3. Frontend Pages

### Design System

- **Theme:** Dark mode only. Zinc/Slate gray background tones, subtle borders.
- **Accent colors:** Blue (primary actions), Green (success/completed), Red (error/failed), Amber (warning/pending), Purple (auto-release/special actions).
- **Typography:** System font stack (Inter preferred if available).
- **Layout:** Fixed left sidebar (240px) + scrollable main content area. No top navbar.
- **Components:** Shadcn/ui primitives — `Card`, `Table`, `Badge`, `Button`, `Dialog`, `Select`, `Input`, `Tabs`, `Tooltip`, `Collapsible`, `ScrollArea`.

### Global Behaviors

- **Polling:** All pages auto-refresh data every 5 seconds via a shared `usePolling` hook.
- **Navigation:** React Router with sidebar links. Active page highlighted.
- **Loading states:** Skeleton loaders on first load, seamless background refresh on subsequent polls.
- **Error handling:** Toast notifications for API errors. Retry button for failed requests.

---

### Page 1: Overview (Home)

**Route:** `/`

**Purpose:** Dense command center providing an at-a-glance system health view.

**Data sources:** `GET /api/status`, `GET /api/activity`, `GET /api/pipeline`

**Layout:**

```
+----------------------------------------------------------+
|  [Running Agents]  [Pending Tasks]  [Awaiting]  [Done]   |  <- KPI Cards row
+----------------------------------------------------------+
|  pending -> assigned -> awaiting -> in_progress -> done   |  <- Pipeline Flow
+----------------------------------------------------------+
|  Recent Activity (3:2)     |  Agent Status Grid           |  <- Two columns
|  - Executor assigned...    |  [Director]  idle  ●         |
|  - Planner completed...    |  [Planner]   running ●       |
|  - Worker failed...        |  [Researcher] idle  ●        |
|                            |  [Executor]  running ●       |
|                            |  [Auditor]   idle  ●         |
|                            |  [Improvement] idle ●        |
+----------------------------------------------------------+
```

**Components:**

1. **KpiCards** (4 cards in a row)
   - Running Agents: count + "of N total" secondary text
   - Pending Tasks: count + "N assigned" secondary text
   - Awaiting Review: count of pending releases + "N rules active" secondary text
   - Completed Today: count + success rate percentage secondary text
   - Each card: large number, label, secondary stat, subtle colored left border
   - Click any card: navigates to the relevant page (Agents, Tasks, Releases, Tasks filtered by completed)

2. **TaskPipeline** (horizontal flow)
   - Horizontal connected boxes showing each status stage: pending -> assigned -> awaiting_release -> in_progress -> completed | failed
   - Each box shows the count for that status
   - Color-coded: gray (pending), blue (assigned), amber (awaiting), blue (in_progress), green (completed), red (failed)
   - Animated transitions when counts change

3. **ActivityFeed** (left column, 60% width)
   - Timeline-style vertical list, newest at top
   - Each entry: colored dot by event type, agent name badge, action description, relative timestamp ("2m ago")
   - Click any entry: navigates to the associated task detail page
   - Shows last 20 items, "View All" link to a scrollable view

4. **AgentStatusGrid** (right column, 40% width)
   - Card per L1 agent (6 cards in a 2x3 or 3x2 grid)
   - Each card: agent name, status dot (green=idle, blue=running, red=error), current task title if running, run count
   - Click any agent: navigates to agent detail page

---

### Page 2: Requests

**Route:** `/requests`

**Purpose:** Submit new work to the Ultra Agent system and track request history.

**Data sources:** `POST /api/requests`, `GET /api/requests`

**Layout:**

```
+----------------------------------------------------------+
|  Submit New Request                                       |
|  [================================ text area =========]   |
|  Priority: [===slider/select===]     [Submit Request]     |
+----------------------------------------------------------+
|  Request History                                          |
|  Title          | Status  | Priority | Created  | Done    |
|  Build login... | ● prog  | 7        | 2m ago   | -       |
|  Fix billing... | ● done  | 8        | 1h ago   | 45m ago |
+----------------------------------------------------------+
```

**Components:**

1. **RequestInput** (top section)
   - Large multi-line text area (title + description combined or separate fields)
   - Priority selector: dropdown 1-10 with color indicators (1=low gray, 10=critical red)
   - Submit button: blue, disabled while submitting, shows spinner
   - On submit: POST to `/api/requests`, clear form, show success toast, new request appears in history

2. **RequestHistory** (table below)
   - Columns: Title, Status (color-coded badge), Priority (number with color), Created (relative time), Completed (relative time or dash), Subtask Progress (e.g., "2/5")
   - Status badges: pending=gray, assigned=blue, in_progress=blue, awaiting_release=amber, completed=green, failed=red
   - Click any row: navigates to `/tasks/:id` (task detail with full timeline)
   - Pagination at bottom

**Cross-links:**
- Row click -> Task Detail page
- Status badge click -> Tasks page filtered by that status

---

### Page 3: Tasks

**Route:** `/tasks` and `/tasks/:id`

**Purpose:** Browse, filter, and inspect all tasks in the system with deep drill-down into execution timeline and subtask decomposition.

**Data sources:** `GET /api/tasks`, `GET /api/tasks/:id`, `GET /api/tasks/:id/timeline`, `GET /api/tasks/:id/subtasks`

**Layout (list view):**

```
+----------------------------------------------------------+
|  Filters: [Status v] [Agent v] [Priority ===] [Search__] |
+----------------------------------------------------------+
|  Title           | Status | Agent    | Pri | Created | Dur|
|  Build login...  | ● prog | Executor | 7   | 2m ago  | 5m |
|  > (expanded detail when clicked)                         |
+----------------------------------------------------------+
```

**Layout (detail view, expanded or `/tasks/:id`):**

```
+----------------------------------------------------------+
|  < Back to Tasks                                          |
|  Build Login Page          [● in_progress]  Priority: 7   |
|  Created: 2026-04-05 09:00  Started: 09:01  Agent: Exec  |
+----------------------------------------------------------+
|  Execution Timeline                                       |
|  ● 09:00  [Director]  Created task                        |
|  ● 09:00  [Director]  Assigned to Planner                 |
|  ● 09:01  [Planner]   Decomposed into 3 subtasks          |
|    > expanded: { subtasks: [...] }                         |
|  ● 09:02  [Researcher] Started research subtask            |
|  ● 09:10  [Researcher] Completed research                  |
|  ● 09:11  [Executor]  Started implementation               |
|  ● 09:30  [Executor]  Awaiting release                     |
+----------------------------------------------------------+
|  Subtask Tree                                             |
|  ├── Design schema         ✅ Planner   3m                |
|  │   └── Research schemas  ✅ Researcher 8m               |
|  ├── Implement login       ⏳ Executor  19m...            |
|  └── Write tests           ○ (pending)                    |
+----------------------------------------------------------+
|  ▶ Input Data   (collapsible JSON viewer)                 |
|  ▶ Output Data  (collapsible JSON viewer)                 |
+----------------------------------------------------------+
```

**Components:**

1. **TaskList** (filterable table)
   - Filter bar: status multi-select dropdown, agent dropdown, priority range slider, text search input
   - Table columns: Title, Status Badge, Assigned Agent, Priority, Created (relative), Duration
   - Click row: expands inline to show TaskDetail, or navigates to `/tasks/:id`

2. **TaskDetail** (full detail view)
   - Header: title, task ID (copyable), status badge, priority badge, timestamps (created, started, completed), assigned agent link
   - Error banner: if `status = 'failed'`, show red banner with `error_message`

3. **TaskTimeline** (vertical timeline)
   - Chronological list of events from `/api/tasks/:id/timeline`
   - Each entry: colored dot (color-coded by agent), agent name as clickable badge, action description, timestamp
   - Expandable entries: click to reveal full `data_json` content (JSON viewer)
   - Agent names link to `/agents/:id`
   - Session IDs link to `/sessions/:id`

4. **SubtaskTree** (indented tree)
   - Recursive tree from `/api/tasks/:id/subtasks`
   - Each node: status icon, title, assigned agent badge, duration
   - Status icons: checkmark (completed), spinner (in_progress), clock (pending), x (failed), pause (blocked)
   - Click any subtask: navigates to its own task detail view
   - Collapsible branches for deep trees

5. **Input/Output panels** (collapsible)
   - JSON syntax-highlighted viewers for `input_data` and `output_data`
   - Copy-to-clipboard button

**Cross-links:**
- Agent badges -> Agent Detail
- Session references -> Session Replay
- Subtask nodes -> Task Detail (recursive)
- Release references -> Work Releases

---

### Page 4: Agents

**Route:** `/agents` and `/agents/:id`

**Purpose:** Visualize the agent hierarchy and inspect individual agent performance.

**Data sources:** `GET /api/agents`, `GET /api/agents/:id`, `GET /api/agents/:id/sessions`, `GET /api/agents/hierarchy`

**Layout:**

```
+----------------------------------------------------------+
|  Agent Hierarchy                                          |
|                                                           |
|              [Director L0]                                |
|          /    |    |    |   \    \                        |
|     [Plan] [Lib] [Res] [Exe] [Aud] [Imp]  <- L1          |
|              |         / \                                |
|           [sub]    [sub] [sub]             <- L2          |
|                      |                                    |
|                   [worker]                 <- L3          |
+----------------------------------------------------------+
|  Agent Detail Panel (shown when node clicked)             |
|  Executor  [● running]  L1                                |
|  Runs: 42  Errors: 3  Success: 93%  Last: 10m ago        |
|                                                           |
|  Current Task: Build login page (in_progress)             |
|                                                           |
|  Recent Tasks:                                            |
|  Build header    ✅  30m   |  Fix sidebar  ✅  15m        |
|                                                           |
|  Sessions:                                                |
|  sess-001  completed  15s  |  sess-002  failed  8s        |
+----------------------------------------------------------+
```

**Components:**

1. **AgentHierarchy** (tree/org-chart visualization)
   - Tree layout with Director at top, L1 agents below, dynamically spawned L2/L3 below their parents
   - Each node is a card: agent name, type label, level badge, status dot (green=idle, blue=running, red=error)
   - Secondary text: run count / error count
   - Click any node: opens the detail panel below (or as a side panel)
   - Nodes pulse subtly when status is "running"

2. **AgentDetail** (detail panel)
   - Stats row: total runs, errors, success rate (%), last run timestamp
   - Current task card: if agent is running, show the task title + status + link to task detail
   - Recent tasks table: last 10 tasks with title, status, duration. Click -> Task Detail
   - Session history table: last 10 sessions with status, duration, success indicator. Click -> Session Replay
   - Error log: if `error_count > 0`, show recent errors with timestamps

**Cross-links:**
- Current task -> Task Detail
- Task history rows -> Task Detail
- Session history rows -> Session Replay
- Child agent nodes -> their own Agent Detail

---

### Page 5: Work Releases

**Route:** `/releases`

**Purpose:** Human approval gate. Review, approve, reject, or auto-release agent work products.

**Data sources:** `GET /api/releases`, `POST /api/releases/:id/approve`, `POST /api/releases/:id/reject`, `POST /api/releases/:id/auto-release`, `GET /api/rules`, `DELETE /api/rules/:id`

**Layout:**

```
+----------------------------------------------------------+
|  Pending Releases (3)                    [Approve All ▼]  |
+----------------------------------------------------------+
|  ┌─────────────────────────────────────────────────────┐  |
|  │ Plan: Decompose login page build                    │  |
|  │ Agent: Planner (L1)  Action: plan                   │  |
|  │ Input: "Build a login page for the admin portal"    │  |
|  │ Description: Breaking into 3 subtasks...            │  |
|  │                                                     │  |
|  │ [✓ Approve]  [✗ Reject]  [⟳ Auto-Release]          │  |
|  └─────────────────────────────────────────────────────┘  |
+----------------------------------------------------------+
|  Auto-Release Rules                                       |
|  Agent Type | Action | Skill | Pattern | Enabled | Fires  |
|  executor   | exec   | -     | -       | [on]    | 12     |
|  planner    | plan   | -     | -       | [on]    | 8      |
|                                          [Delete]         |
+----------------------------------------------------------+
|  Release History                                          |
|  Title         | Agent   | Status    | Reviewed           |
|  Plan: login   | Planner | approved  | 5m ago             |
|  Execute: css  | Exec    | rejected  | 1h ago             |
+----------------------------------------------------------+
```

**Components:**

1. **ReleaseQueue** (pending releases)
   - Cards for each pending release, prominent at the top
   - Each card: title, agent name + level badge, action type badge (colored: plan=blue, research=purple, execute=green, review=amber), input preview (truncated), description
   - Three action buttons per card:
     - **Approve** (green): POST approve, card animates out
     - **Reject** (red): opens small dialog for optional rejection reason, POST reject
     - **Auto-Release** (purple): POST auto-release, creates rule, card animates out
   - **Batch "Approve All"** button: confirmation dialog ("Approve all N pending releases?"), approves each sequentially
   - Empty state: "No pending releases" with checkmark icon

2. **AutoReleaseRules** (rules table)
   - Table columns: Agent Type, Action Type, Skill ID, Title Pattern, Enabled (toggle switch), Fire Count, Created From, Delete button
   - Toggle switch: inline PATCH to enable/disable (via PUT to a new endpoint or toggle via POST)
   - Delete button: confirmation dialog, DELETE rule
   - "Created From" links to the original release

3. **ReleaseHistory** (recently reviewed)
   - Table of approved/rejected/auto-released releases
   - Columns: Title, Agent, Status Badge, Reviewed At (relative time)
   - Click row: shows release detail in a dialog

**Cross-links:**
- Task title in release -> Task Detail
- Agent name in release -> Agent Detail

---

### Page 6: Skills

**Route:** `/skills` and `/skills/:id`

**Purpose:** Browse the skill registry, inspect skill templates, view invocation history, and test-run skills with real browser automation.

**Data sources:** `GET /api/skills`, `GET /api/skills/:id`, `GET /api/skills/:id/invocations`, `POST /api/skills/:id/test`

**Layout:**

```
+----------------------------------------------------------+
|  Skills  [Search_____________]  [Category: All ▼]         |
+----------------------------------------------------------+
|  Name       | NS     | Cat    | ✓/✗    | Rate | Ver | Used|
|  css_login  | jf.ag  | browser| 45/2   | ████ | 3   | 2m  |
|  pay_check  | jf.ag  | browser| 20/1   | ████ | 2   | 1h  |
+----------------------------------------------------------+
|  Skill Detail (shown when row clicked)                    |
|  css_login v3  [browser]  jfchong.alliedgroup             |
|                                                           |
|  Template: (syntax-highlighted JSON viewer)               |
|  { "steps": [...], "inputs": {...} }                      |
|                                                           |
|  Browser Category: [SS-SM]                                |
|                                                           |
|  Invocation History:                                      |
|  Date      | Input         | Output      | Dur  | Status  |
|  10:00     | A-12-3        | bal: 150    | 12s  | ✅      |
|                                                           |
|  Success Rate: ████████████████░░ 96%                     |
|                                                           |
|  [▶ Test Run]                                             |
+----------------------------------------------------------+
```

**Components:**

1. **SkillList** (searchable table)
   - Search bar: filters by name or description (debounced 300ms)
   - Category dropdown filter
   - Table columns: Name, Namespace, Category, Success/Failure counts, Success Rate (colored bar), Version, Last Used (relative)
   - Click row: expands to show SkillDetail

2. **SkillDetail** (expanded detail)
   - Header: skill name, version badge, category badge, namespace, active/inactive indicator
   - Template viewer: syntax-highlighted JSON showing the full `agent_template`, `data_schema`, `output_schema`
   - Browser category badge (if applicable): colored badge showing SS-SM, SS-MM, MS-SM, or MS-MM
   - Success rate chart: horizontal bar chart showing success vs failure ratio
   - Invocation history table: recent invocations with date, input data (truncated), output data (truncated), duration, status badge. Click row to expand full JSON.

3. **SkillTestRunner** (modal dialog)
   - Opened by clicking "Test Run" button on a skill
   - Input form: dynamically generated from `data_schema` — one input field per schema key with appropriate types
   - Headless toggle: checkbox (default: on)
   - "Run" button: starts test, button becomes disabled with spinner
   - Live progress display: step-by-step list that populates as steps complete
     - Each step: step number, action type icon, target, status indicator (spinner -> checkmark/x), duration
   - On completion: shows output data in a JSON viewer, link to screenshot if available
   - On failure: shows error message with the failed step highlighted in red
   - "Close" button to dismiss

**Cross-links:**
- Invocation task_id -> Task Detail
- Invocation agent_id -> Agent Detail

---

### Page 7: Sessions

**Route:** `/sessions` and `/sessions/:id`

**Purpose:** Browse all agent sessions and replay step-by-step browser recordings.

**Data sources:** `GET /api/sessions`, `GET /api/sessions/:id`, `GET /api/sessions/:id/recordings`

**Layout:**

```
+----------------------------------------------------------+
|  Sessions  [Agent ▼]  [Status ▼]  [Browser Cat ▼]        |
+----------------------------------------------------------+
|  Agent       | Task          | Cat  | Status | Dur | Start|
|  Worker-001  | Check balance | SS-SM| ✅ done| 15s | 10:00|
|  Executor    | Build login   | -    | ✅ done| 30m | 09:01|
|  Worker-002  | Pay bill      | SS-SM| ❌ fail| 8s  | 09:50|
+----------------------------------------------------------+
|  Session Replay (shown when row clicked)                  |
|  Session: sess-001  Agent: Worker-001  Status: completed  |
|                                                           |
|  Step | Action    | Target           | Result  | Duration |
|  1    | login     | csshome.info     | ✅      | 3.2s     |
|  2    | navigate  | /accounts        | ✅      | 1.5s     |
|  3    | fill      | #unit-number     | ✅      | 0.2s     |
|  4    | click     | #search-btn      | ✅      | 0.8s     |
|  5    | extract   | .balance-amount  | 150.00  | 0.1s     |
|                                                           |
|  Error: (red banner, only for failed sessions)            |
+----------------------------------------------------------+
```

**Components:**

1. **SessionList** (filterable table)
   - Filter bar: agent dropdown, status dropdown, browser category dropdown
   - Table columns: Agent Name, Task Title, Browser Category, Status (colored badge), Duration, Started At (relative)
   - Status colors: running=blue (animated dot), completed=green, failed=red, timeout=amber
   - Click row: expands to show SessionReplay

2. **SessionReplay** (step-by-step view)
   - Header: session ID, agent name (linked), task title (linked), browser category badge, status badge, total duration
   - Recording table: step number, action type (colored badge), target, value, result, duration
   - Action type colors: auto_login=amber, navigate=blue, click=green, fill=purple, screenshot=gray, wait=slate, extract=orange, assert=cyan
   - For failed sessions: the failed step has a red background, error message displayed below the table in a red banner
   - Summary text if available
   - Output snapshot: collapsible JSON viewer

**Cross-links:**
- Agent name -> Agent Detail
- Task title -> Task Detail
- Parent session -> Session Replay (for nested sessions)

---

### Page 8: Improvements

**Route:** `/improvements`

**Purpose:** View the system's self-improvement log — patterns it has discovered, approach ratings, and optimization suggestions.

**Data sources:** `GET /api/improvements`, `GET /api/improvements/stats`

**Layout:**

```
+----------------------------------------------------------+
|  Improvements                                             |
|  [Total: 35]  [Avg Impact: +0.42]  [Top: success_pattern]|
+----------------------------------------------------------+
|  Filters: [Category ▼]  [Agent ▼]                        |
+----------------------------------------------------------+
|  Cat           | Agent    | Summary              | Impact |
|  success_pat   | Improve  | Parallel decomp +40% | ████▓  |
|  failure_pat   | Auditor  | Missing validation   | ▓▓▓▓░  |
|  skill_refine  | Improve  | Optimized CSS steps  | ████░  |
+----------------------------------------------------------+
```

**Components:**

1. **Stats summary** (top cards row)
   - Total Patterns Found
   - Average Impact Score (colored: green if positive, red if negative)
   - Top Improving Areas (category with highest positive average)
   - Cards are informational, not clickable

2. **ImprovementLog** (filterable table)
   - Filter bar: category multi-select, agent dropdown
   - Table columns: Category Badge, Agent Name, Task Title, Summary, Impact Score Bar, Action Taken, Created At
   - Impact score visualization: horizontal bar from center. Positive = green bar extending right. Negative = red bar extending left. Range -1.0 to +1.0.
   - Click row: expands to show full details and action taken text
   - Category badges color-coded:
     - success_pattern = green
     - failure_pattern = red
     - approach_rating = blue
     - toolkit_feedback = purple
     - skill_refinement = amber
     - process_suggestion = cyan

**Cross-links:**
- Task title -> Task Detail
- Agent name -> Agent Detail

---

### Page 9: Settings

**Route:** `/settings`

**Purpose:** System configuration — config values, credentials, cron schedules, and auto-release rules.

**Data sources:** `GET /api/config`, `PUT /api/config/:key`, `GET /api/credentials`, `POST /api/credentials`, `DELETE /api/credentials/:id`, `GET /api/cron`, `POST /api/cron`, `PUT /api/cron/:id`, `DELETE /api/cron/:id`, `GET /api/rules`, `DELETE /api/rules/:id`

**Layout:**

```
+----------------------------------------------------------+
|  Settings                                                 |
+----------------------------------------------------------+
|  System Configuration                                     |
|  ┌───────────────────────────────────────────────┐        |
|  │ default_namespace    │ jfchong.alliedgroup [✎] │       |
|  │ max_concurrent_agents│ 5                   [✎] │       |
|  │ agent_cooldown_secs  │ 30                  [✎] │       |
|  │ stuck_timeout_mins   │ 10                  [✎] │       |
|  └───────────────────────────────────────────────┘        |
+----------------------------------------------------------+
|  Credentials                                              |
|  ┌───────────────────────────────────────────────┐        |
|  │ Domain        │ Label         │ Type  │ Action │       |
|  │ csshome.info  │ CSS Portal    │ pass  │ [Del]  │       |
|  │ [+ Add Credential]                             │       |
|  └───────────────────────────────────────────────┘        |
+----------------------------------------------------------+
|  Cron Schedules                                           |
|  ┌───────────────────────────────────────────────────┐    |
|  │ Expression   │ Agent    │ On │ Fires │ Last  │ Next│   |
|  │ 0 */6 * * *  │ Improve  │[●] │ 28    │ 6:00  │12:00│  |
|  │ [+ Add Schedule]                                   │   |
|  └───────────────────────────────────────────────────┘    |
+----------------------------------------------------------+
|  Auto-Release Rules                                       |
|  (same table as on Releases page, duplicated here)        |
+----------------------------------------------------------+
```

**Components:**

1. **ConfigEditor** (key-value cards)
   - Each config row: key label, current value, edit button (pencil icon)
   - Edit mode: value becomes an inline text input with Save/Cancel buttons
   - On save: PUT to `/api/config/:key`, show success toast
   - No add/delete — config keys are managed by the system

2. **CredentialManager** (table with add/delete)
   - Table columns: Site Domain, Label, Auth Type, Created At, Delete button
   - Never displays passwords or credential JSON content
   - "Add Credential" button opens a dialog:
     - Fields: Site Domain, Label, Auth Type (dropdown: password, oauth, api_key, cookie), Credentials JSON (textarea, input type varies by auth_type)
     - Submit: POST to `/api/credentials`
   - Delete button: confirmation dialog, then DELETE

3. **CronScheduler** (table with CRUD)
   - Table columns: Cron Expression, Agent Name, Enabled Toggle, Fire Count, Max Fires, Last Fired, Next Fire, Edit/Delete buttons
   - Enabled toggle: inline PUT to update `is_enabled`
   - "Add Schedule" button opens a dialog:
     - Fields: Agent (dropdown of all agents), Cron Expression (text input with helper text showing format), Task Template (JSON textarea), Max Fires (optional number input)
     - Submit: POST to `/api/cron`
   - Edit button: opens same dialog pre-filled, submits PUT
   - Delete button: confirmation dialog, then DELETE

4. **AutoReleaseRules** (same component as on Releases page)
   - Shared component, identical behavior

---

## 4. Selenium/Playwright Integration

### Overview

The Skills page includes a "Test Run" feature that executes a skill's browser automation steps in a real browser via Playwright. This enables verification of skill templates without dispatching a full agent workflow.

### Architecture

```
React (SkillTestRunner modal)
    |  POST /api/skills/:id/test  { input_data: {...} }
    v
dashboard-server.py
    |  subprocess.run(["python", "scripts/browser-runner.py", ...])
    v
browser-runner.py
    |  Reads skill template + input data from stdin/args
    |  Loads credentials from ultra.db (credentials table)
    v
Playwright (Chromium)
    |  Executes steps: auto_login, navigate, click, fill, wait, extract, screenshot, assert
    v
Step-by-step results JSON -> stdout -> dashboard-server.py -> React
```

### browser-runner.py

**Location:** `scripts/browser-runner.py`

**Input:** JSON on stdin:
```json
{
  "skill_id": "skill-001",
  "skill_template": {
    "steps": [
      {"action": "auto_login", "domain": "csshome.info"},
      {"action": "navigate", "url": "https://csshome.info/accounts"},
      {"action": "fill", "selector": "#unit-number", "value": "{{unit_number}}"},
      {"action": "click", "selector": "#search-btn"},
      {"action": "wait", "selector": ".results-table", "timeout": 5000},
      {"action": "extract", "selector": ".balance-amount", "output_key": "balance"},
      {"action": "screenshot", "filename": "result.png"}
    ]
  },
  "input_data": {
    "unit_number": "A-12-3"
  },
  "db_path": "C:/Users/jfcho/Desktop/CoWork/MultiAgent/ultra.db",
  "headless": true,
  "screenshot_dir": "C:/Users/jfcho/Desktop/CoWork/MultiAgent/logs/screenshots"
}
```

**Output:** JSON on stdout:
```json
{
  "status": "completed",
  "duration_seconds": 15.2,
  "steps": [
    {"step_number": 1, "action_type": "auto_login", "target": "csshome.info", "result": "success", "duration_ms": 3200},
    {"step_number": 2, "action_type": "navigate", "target": "https://csshome.info/accounts", "result": "success", "duration_ms": 1500}
  ],
  "output_data": {"balance": "150.00"},
  "screenshot_path": "logs/screenshots/skill-001-test-20260405T100000.png",
  "error": null
}
```

**Supported actions:**

| Action | Parameters | Description |
|--------|-----------|-------------|
| `auto_login` | `domain` | Look up credentials in DB, navigate to login page, fill username/password, submit |
| `navigate` | `url` | Navigate to URL, wait for load |
| `click` | `selector`, `wait_after` (optional ms) | Click element, optionally wait after |
| `fill` | `selector`, `value` | Clear and fill input. `value` supports `{{variable}}` interpolation from input_data |
| `wait` | `selector`, `timeout` (ms) | Wait for element to appear |
| `extract` | `selector`, `output_key`, `attribute` (optional) | Extract text content (or attribute) from element, store in output_data |
| `screenshot` | `filename` | Take full-page screenshot, save to screenshot_dir |
| `assert` | `selector`, `expected`, `attribute` (optional) | Assert element text/attribute matches expected value |

**Credential handling:**
- `auto_login` reads from the `credentials` table using `site_domain` as the lookup key.
- Credentials are loaded server-side only. They never appear in the step results, API responses, or logs.
- Step results log only `"target": "csshome.info"` for auto_login, never the actual username or password.

**Error handling:**
- If any step fails, execution stops. The failed step's result is set to the error message. Subsequent steps are marked as "skipped".
- Timeout: if the total execution exceeds 120 seconds, the browser process is killed and a timeout error is returned.
- Browser crash: caught and returned as a step failure.

### Dependencies

```
pip install playwright
playwright install chromium
```

These are only required on machines that will use the "Test Run" feature. The dashboard itself works without Playwright installed — the "Test Run" button simply shows an error if Playwright is not available.

---

## 5. Project Structure

```
C:\Users\jfcho\Desktop\CoWork\MultiAgent\
├── dashboard/                          # React app (NEW)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── postcss.config.js
│   ├── components.json                 # Shadcn/ui config
│   ├── index.html
│   ├── public/
│   │   └── favicon.ico
│   ├── src/
│   │   ├── main.tsx                    # React entry point
│   │   ├── App.tsx                     # Router + Layout (sidebar + content)
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx         # Fixed left sidebar with nav links
│   │   │   │   └── Header.tsx          # Page title bar (within content area)
│   │   │   ├── overview/
│   │   │   │   ├── KpiCards.tsx        # 4 KPI metric cards
│   │   │   │   ├── TaskPipeline.tsx    # Horizontal status flow
│   │   │   │   ├── ActivityFeed.tsx    # Timeline-style recent events
│   │   │   │   └── AgentStatusGrid.tsx # L1 agent status cards
│   │   │   ├── requests/
│   │   │   │   ├── RequestInput.tsx    # Text area + priority + submit
│   │   │   │   └── RequestHistory.tsx  # Request history table
│   │   │   ├── tasks/
│   │   │   │   ├── TaskList.tsx        # Filterable task table
│   │   │   │   ├── TaskDetail.tsx      # Full task detail view
│   │   │   │   ├── TaskTimeline.tsx    # Vertical event timeline
│   │   │   │   └── SubtaskTree.tsx     # Recursive subtask tree
│   │   │   ├── agents/
│   │   │   │   ├── AgentHierarchy.tsx  # Tree/org-chart visualization
│   │   │   │   └── AgentDetail.tsx     # Agent stats + history
│   │   │   ├── releases/
│   │   │   │   ├── ReleaseQueue.tsx    # Pending release cards with actions
│   │   │   │   └── AutoReleaseRules.tsx# Rules table with toggle/delete
│   │   │   ├── skills/
│   │   │   │   ├── SkillList.tsx       # Searchable skill table
│   │   │   │   ├── SkillDetail.tsx     # Template viewer + invocations
│   │   │   │   └── SkillTestRunner.tsx # Test run modal with live progress
│   │   │   ├── sessions/
│   │   │   │   ├── SessionList.tsx     # Filterable session table
│   │   │   │   └── SessionReplay.tsx   # Step-by-step recording view
│   │   │   ├── improvements/
│   │   │   │   └── ImprovementLog.tsx  # Improvement table + stats
│   │   │   ├── settings/
│   │   │   │   ├── ConfigEditor.tsx    # Key-value config editor
│   │   │   │   ├── CredentialManager.tsx# Credential CRUD (no passwords shown)
│   │   │   │   └── CronScheduler.tsx   # Cron schedule CRUD
│   │   │   └── ui/                     # Shadcn/ui primitives (auto-generated)
│   │   │       ├── button.tsx
│   │   │       ├── card.tsx
│   │   │       ├── badge.tsx
│   │   │       ├── table.tsx
│   │   │       ├── dialog.tsx
│   │   │       ├── select.tsx
│   │   │       ├── input.tsx
│   │   │       ├── textarea.tsx
│   │   │       ├── tabs.tsx
│   │   │       ├── tooltip.tsx
│   │   │       ├── collapsible.tsx
│   │   │       ├── scroll-area.tsx
│   │   │       ├── switch.tsx
│   │   │       ├── skeleton.tsx
│   │   │       ├── toast.tsx
│   │   │       └── toaster.tsx
│   │   ├── lib/
│   │   │   ├── api.ts                  # API client (fetch wrapper with base URL)
│   │   │   └── utils.ts               # cn(), formatDuration(), relativeTime()
│   │   ├── hooks/
│   │   │   ├── usePolling.ts           # 5-second polling hook with cleanup
│   │   │   └── useApi.ts              # Generic fetch + loading + error hook
│   │   └── styles/
│   │       └── globals.css             # Tailwind base + dark theme overrides
│   └── dist/                           # Production build output (gitignored)
│
├── scripts/
│   ├── dashboard-server.py             # Full API server (replaces release-server.py)
│   ├── browser-runner.py               # Playwright skill executor (NEW)
│   ├── release-server.py               # (DEPRECATED — kept for reference)
│   ├── db-init.py
│   ├── db-utils.py
│   ├── cron-manager.py
│   ├── dispatch-agent.sh
│   ├── health-check.py
│   ├── ultra.py
│   └── e2e-verify.py
│
├── logs/
│   └── screenshots/                    # Playwright screenshots from test runs
│
├── ultra.db                            # SQLite database (all state)
├── ui/                                 # OLD vanilla UI (superseded by dashboard/)
└── startup.bat                         # Updated to serve dashboard/dist/
```

---

## 6. Data Flow

### Normal Operation

```
User Browser (React SPA on localhost:53800)
    ↕ HTTP/JSON (5-second polling for reads, immediate for writes)
dashboard-server.py (Python, port 53800)
    ↕ SQLite queries (per-request connections, WAL mode)
ultra.db
    ↕ Also read/written by:
cron-manager.py (1-min tick, dispatches agents)
dispatch-agent.sh (spawns claude -p sessions)
claude -p agents (L1-L3, read/write tasks, events, memory, etc.)
```

### Request Submission Flow

```
1. User types request in dashboard → POST /api/requests
2. dashboard-server.py creates task in ultra.db
3. dashboard-server.py spawns: dispatch-agent.sh director <task_id>
4. Director (L0) reads task, decomposes, assigns to L1 agents
5. L1 agents create subtasks, events, work releases
6. Dashboard polls /api/status, /api/activity → shows live updates
7. Work releases appear on Releases page → user approves/rejects
8. Agents continue work → tasks complete → events logged
9. Dashboard shows completed status via polling
```

### Skill Test Run Flow

```
1. User clicks "Test Run" on skill → fills input data → clicks "Run"
2. React POSTs to /api/skills/:id/test with input data
3. dashboard-server.py loads skill template from ultra.db
4. dashboard-server.py spawns: python scripts/browser-runner.py
   - Passes skill template + input data via stdin (JSON)
5. browser-runner.py:
   a. Launches Playwright Chromium (headless by default)
   b. Loads credentials from ultra.db for auto_login domains
   c. Executes each step sequentially
   d. Captures timing, results, screenshots
   e. Writes JSON result to stdout
6. dashboard-server.py reads stdout, returns to React
7. React shows step-by-step results in SkillTestRunner modal
```

---

## 7. Migration from Existing UI

### What Changes

| Component | Before | After |
|-----------|--------|-------|
| Server | `scripts/release-server.py` | `scripts/dashboard-server.py` |
| Frontend | `ui/` (vanilla HTML/CSS/JS) | `dashboard/dist/` (React build) |
| Port | 53800 | 53800 (unchanged) |
| API | 4 endpoints (releases + rules + status) | 40+ endpoints (full CRUD for all resources) |
| Static serving | `ui/index.html`, `ui/style.css`, `ui/app.js` | `dashboard/dist/index.html` + Vite-hashed assets |

### Backward Compatibility

All existing API endpoints retain their exact request/response shapes:

- `GET /api/releases?status=...` — same response
- `POST /api/releases/:id/approve` — same response
- `POST /api/releases/:id/reject` — same response
- `POST /api/releases/:id/auto-release` — same response
- `GET /api/rules` — same response
- `DELETE /api/rules/:id` — same response
- `GET /api/status` — same fields, plus additional new fields

### Migration Steps

1. Build the React app: `cd dashboard && npm run build`
2. Replace `release-server.py` invocation with `dashboard-server.py` in `startup.bat`
3. `release-server.py` is kept in `scripts/` but marked deprecated (header comment)
4. The `ui/` directory is left in place for reference but is no longer served

### Vite Dev Proxy Configuration

`dashboard/vite.config.ts`:
```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:53800'
    }
  }
})
```

During development: run `dashboard-server.py` on 53800 (API only), run `npm run dev` on 5173 (React with hot reload, proxies API calls to 53800).

---

## 8. Implementation Notes

### Polling Strategy

The `usePolling` hook:
- Calls the API endpoint immediately on mount
- Sets up a 5-second interval for subsequent calls
- Cleans up the interval on unmount
- Skips the current poll if the previous one is still in flight (prevents stacking)
- Returns `{ data, loading, error, refetch }` for manual refresh after mutations

### Database Connection Management

- `dashboard-server.py` opens a new SQLite connection per request (not pooled)
- Each connection sets `PRAGMA journal_mode=WAL` to allow concurrent reads while agents write
- Connections are closed in a `finally` block to prevent leaks
- `check_same_thread=False` is set since the HTTP server may handle requests from different threads

### Error Handling

- API errors return `{"error": "Human-readable message"}` with appropriate HTTP status (400, 404, 409, 500)
- Frontend shows toast notifications for errors
- Network failures show a subtle "Connection lost" banner that auto-dismisses on recovery
- Polling continues even after errors (resilient to transient failures)

### Security Considerations

- The dashboard is intended for local development use only (localhost)
- CORS allows all origins (same as existing release-server.py)
- Credentials are never exposed through the API (only domain, label, auth_type)
- No authentication on the API (local tool assumption)
- If remote access is ever needed, add a session token middleware

### Performance

- SQLite WAL mode handles concurrent reads from the dashboard + writes from agents
- Polling at 5-second intervals is light enough for SQLite (each poll = 1-3 simple queries)
- React renders only changed data (React's virtual DOM diffing)
- Tables use pagination to avoid loading thousands of rows
- Activity feed is limited to the most recent N items
