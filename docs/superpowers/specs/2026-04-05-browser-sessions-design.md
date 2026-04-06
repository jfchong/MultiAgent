# Browser Integration & Session Recording — Design Spec

## Overview

Extend the Ultra Agent system with two capabilities:

1. **Browser Integration** — Workers can control Chrome browser tabs via the Claude Chrome Extension to navigate websites, fill forms, click elements, and extract data.
2. **Session Recording** — Every agent dispatch is recorded as an individual session. Successful browser sessions are saved as reusable skill templates with detailed step-by-step recordings for audit.

## Principles

- **Workers are lean.** They receive only the context needed for their browser category. The Planner/Sub-Agent does the thinking; Workers just execute.
- **Credentials are infrastructure.** Login details are preconfigured per site domain, never passed as task inputs, never logged in recordings.
- **Task inputs are business data.** Unit numbers, owner names, payment amounts — the values that change between invocations.
- **Chrome Extension now, Puppeteer later.** The browser protocol abstracts the execution engine so Workers don't change when the backend swaps.

---

## 1. Worker Browser Categories

Workers that need browser access are tagged with a `browser_category` that defines their operational scope and context weight.

| Category | Code | Scope | Context Weight |
|----------|------|-------|----------------|
| Single Site, Single Motive | `SS-SM` | One URL domain, one action | Lightest — minimal nav instructions |
| Single Site, Multi Motive | `SS-MM` | One URL domain, multiple actions | Light — sequential actions on same site |
| Multi Site, Single Motive | `MS-SM` | Multiple URL domains, one action type | Medium — same action across sites |
| Multi Site, Multi Motive | `MS-MM` | Multiple URL domains, multiple actions | Heaviest — complex cross-site workflows |

**Storage:** `agents.config_json` as `{"browser_category": "SS-SM"}` when the Worker is spawned by the Executor or Sub-Agent.

**Category assignment:** The Sub-Agent (L2) or Executor (L1) determines the category when spawning the Worker based on the task requirements. The category is fixed for the Worker's lifetime.

**Context loading by category:**
- `SS-SM`: Receives one URL, one action spec, credential lookup for one domain
- `SS-MM`: Receives one URL, ordered action list, credential lookup for one domain
- `MS-SM`: Receives URL list, one action spec, credential lookups for each domain
- `MS-MM`: Receives URL list, ordered action plan per site, credential lookups for each domain

---

## 2. Session Recording System

Every agent dispatch (Director through Workers) is recorded as an individual session.

### New Table: `sessions`

```sql
CREATE TABLE sessions (
    session_id      TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(agent_id),
    task_id         TEXT NOT NULL REFERENCES tasks(task_id),
    parent_session_id TEXT REFERENCES sessions(session_id),
    browser_category TEXT,  -- SS-SM, SS-MM, MS-SM, MS-MM, or NULL for non-browser
    status          TEXT NOT NULL DEFAULT 'running',  -- running, completed, failed, timeout
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    duration_seconds REAL,
    success         INTEGER,  -- 1 = successful, 0 = failed
    summary         TEXT,     -- Agent's self-reported summary
    output_snapshot TEXT,     -- JSON: agent's final output
    error_message   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_sessions_agent ON sessions(agent_id);
CREATE INDEX idx_sessions_task ON sessions(task_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_success ON sessions(success);
CREATE INDEX idx_sessions_parent ON sessions(parent_session_id);
```

### New Table: `session_recordings` (browser sessions only)

```sql
CREATE TABLE session_recordings (
    recording_id    TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id),
    step_number     INTEGER NOT NULL,
    action_type     TEXT NOT NULL,  -- navigate, click, fill, screenshot, wait, extract, assert, auto_login
    target          TEXT,           -- URL, CSS selector, or element description
    value           TEXT,           -- Input value (for fill), expected value (for assert)
    result          TEXT,           -- Extracted text, screenshot path, success/fail
    timestamp       TEXT NOT NULL,
    duration_ms     INTEGER,
    UNIQUE(session_id, step_number)
);

CREATE INDEX idx_recordings_session ON session_recordings(session_id);
CREATE INDEX idx_recordings_action ON session_recordings(action_type);
```

### Session Lifecycle

1. `dispatch-agent.sh` creates a `sessions` row (status=running) before launching `claude -p`
2. Browser Workers log each browser action to `session_recordings` as they execute
3. Non-browser agents have a session but no recordings
4. On completion, dispatch script updates the session with final status, duration, and output
5. `parent_session_id` links Worker sessions back to the Executor/Sub-Agent session that spawned them

### Querying Patterns

```sql
-- All successful browser sessions for a skill
SELECT s.session_id, s.duration_seconds, s.browser_category, s.summary
FROM sessions s
JOIN skill_invocations si ON s.task_id = si.task_id
WHERE si.skill_id = ? AND s.success = 1
ORDER BY s.completed_at DESC;

-- Average duration by browser category
SELECT browser_category, AVG(duration_seconds) as avg_duration, COUNT(*) as total
FROM sessions
WHERE success = 1 AND browser_category IS NOT NULL
GROUP BY browser_category;

-- Failed sessions for debugging
SELECT s.session_id, s.error_message, sr.step_number, sr.action_type, sr.target, sr.result
FROM sessions s
JOIN session_recordings sr ON s.session_id = sr.session_id
WHERE s.success = 0
ORDER BY s.completed_at DESC, sr.step_number;
```

---

## 3. Credential Management

Login credentials are preconfigured infrastructure — never passed as task inputs, never logged in session recordings.

### New Table: `credentials`

```sql
CREATE TABLE credentials (
    credential_id   TEXT PRIMARY KEY,
    site_domain     TEXT NOT NULL UNIQUE,  -- e.g., 'csshome.info', 'gmail.com'
    label           TEXT NOT NULL,          -- e.g., 'PPPSU CSS Portal'
    auth_type       TEXT NOT NULL DEFAULT 'password',  -- password, oauth, api_key, cookie
    credentials_json TEXT NOT NULL,         -- {"username": "...", "password": "..."}
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_credentials_domain ON credentials(site_domain);
```

### Security Rules

1. `credentials_json` stores authentication details — in production, this should be encrypted at rest
2. Session recordings log `auto_login: csshome.info` — never the actual username or password
3. Skill templates reference `auto_login` as a built-in action, not credential values
4. Task `input_data` and `output_data` never contain credentials
5. The `credentials` table is excluded from any export or backup that leaves the local machine

### Credential Lookup Flow

1. Skill template step: `{"action": "auto_login", "site": "csshome.info"}`
2. Worker reads: `SELECT * FROM credentials WHERE site_domain = 'csshome.info'`
3. Worker performs login using the retrieved credentials
4. Worker logs to session_recordings: `action_type='auto_login', target='csshome.info', result='success'`
5. No credential values appear in the recording

---

## 4. Browser Protocol

New shared prompt file: `prompts/browser-protocol.md`

**Who receives it:** Only Workers with `browser_category` set in `agents.config_json`. All other agents (Director, L1 agents, Sub-Agents, non-browser Workers) never see it.

### Action Vocabulary

| Action | Purpose | Target | Value |
|--------|---------|--------|-------|
| `auto_login` | Log into a site using stored credentials | Site domain | — |
| `navigate` | Go to a URL | URL | — |
| `click` | Click an element | CSS selector or description | — |
| `fill` | Type into a form field | CSS selector or description | Text to enter |
| `screenshot` | Capture current page state | Label for the screenshot | — |
| `wait` | Wait for element or condition | CSS selector or description | Timeout in ms |
| `extract` | Pull text/data from page | CSS selector or description | — (result stored) |
| `assert` | Verify expected page state | CSS selector or description | Expected value |

### Category Constraints

The protocol instructs Workers based on their category:

- **`SS-SM`:** You will receive ONE site and ONE action. Execute and return. Do not navigate to other sites.
- **`SS-MM`:** You will receive ONE site and MULTIPLE actions. Execute sequentially on the same site. Do not navigate to other sites.
- **`MS-SM`:** You will receive MULTIPLE sites and ONE action type. Execute the same action on each site in order.
- **`MS-MM`:** You will receive MULTIPLE sites and MULTIPLE actions. Follow the action plan exactly as specified.

### Recording Requirement

Every browser action MUST be logged to `session_recordings` immediately after execution. This is mandatory — no action goes unrecorded. Each recording entry includes the step number, action type, target, value, result, and duration.

### Error Handling

1. Page doesn't load → screenshot current state, log error, report failure
2. Element not found → wait up to timeout, screenshot, log error, report failure
3. Unexpected page state → screenshot, log the actual vs expected state, report failure
4. Do NOT retry unless the skill template explicitly includes retry logic
5. On any failure, the session is marked `success = 0` with the error details

---

## 5. Skill Template Saving from Successful Sessions

When a browser Worker session completes successfully, the system saves both the reusable template and the detailed recording.

### Template Structure (saved to `skill_registry.agent_template`)

```json
{
  "browser_category": "SS-MM",
  "steps": [
    {"action": "auto_login", "site": "csshome.info"},
    {"action": "fill", "target": "#unit-number", "value": "{unit_number}"},
    {"action": "fill", "target": "#owner-name", "value": "{owner_name}"},
    {"action": "click", "target": "#search-btn"},
    {"action": "wait", "target": ".results-table", "timeout": 5000},
    {"action": "extract", "target": ".outstanding-amount", "as": "outstanding_amount"},
    {"action": "extract", "target": ".payment-status", "as": "payment_status"},
    {"action": "extract", "target": ".additional-requests", "as": "additional_requests"},
    {"action": "screenshot", "target": "final-state"}
  ],
  "inputs": ["unit_number", "owner_name"],
  "outputs": ["outstanding_amount", "payment_status", "additional_requests"]
}
```

**Placeholders:** `{unit_number}`, `{owner_name}` etc. are replaced with actual values from `skill_invocations.input_data` at execution time.

**Input fields** are pure business data:
- `unit_number` — "B-12-03"
- `owner_name` — "Tan Ah Kow"
- `payment_amount` — "350.00"
- `billing_period` — "Q1 2026"

**Output fields** are data extracted from the browser:
- `outstanding_amount` — "RM 1,250.00"
- `payment_status` — "Overdue"
- `additional_requests` — "Meter reading required"
- `statement_url` — "/downloads/stmt-B1203.pdf"
- `receipt_number` — "RCP-2026-04-0042"
- `last_payment_date` — "2026-02-15"

### Save Flow

**New skill (Executor Path C):**
1. Worker completes successfully → session marked `success = 1`
2. Executor extracts the action sequence from `session_recordings`
3. Executor templatizes: replaces concrete values with `{placeholder}` names
4. Executor saves to `skill_registry` with `agent_template`, `data_schema` (inputs), `output_schema` (outputs)
5. Skill is now reusable

**Existing skill (Executor Path B):**
1. Worker completes successfully → `skill_registry.success_count` incremented
2. If Worker deviated from the template (extra steps, different selectors), flag for Improvement agent review
3. Improvement agent decides: update the template, or log as one-off deviation

**Failed execution:**
1. Worker fails → session marked `success = 0`, `skill_registry.failure_count` incremented
2. Session recordings preserved for debugging
3. If failure rate exceeds threshold (success_rate < 0.7), Improvement agent logs `skill_refinement` suggestion

---

## 6. Dispatch Script Changes

Three additions to `scripts/dispatch-agent.sh`:

### 6a. Session Creation (before launch)

After marking agent as running but before dispatching `claude -p`:

```bash
# Create session record
SESSION_ID=$(python -c "
import sqlite3, uuid, datetime, json
db = sqlite3.connect('$DB_PATH')
sid = str(uuid.uuid4())
browser_cat = None
try:
    config = json.loads('$AGENT_CONFIG_JSON')
    browser_cat = config.get('browser_category')
except:
    pass
db.execute('INSERT INTO sessions (session_id, agent_id, task_id, browser_category, status, started_at) VALUES (?, ?, ?, ?, ?, ?)',
    (sid, '$AGENT_ID', '$TASK_ID', browser_cat, 'running', datetime.datetime.utcnow().isoformat()))
db.commit()
print(sid)
db.close()
")
```

### 6b. Conditional Browser Protocol

After appending the standard protocols, check for browser capability:

```bash
# Append browser protocol if agent has browser_category
BROWSER_CAT=$(echo "$AGENT_JSON" | python -c "
import sys, json
try:
    config = json.loads(json.load(sys.stdin).get('config_json', '{}'))
    print(config.get('browser_category', ''))
except:
    print('')
")

if [ -n "$BROWSER_CAT" ]; then
    if [ -f "$PROJECT_DIR/prompts/browser-protocol.md" ]; then
        echo "" >> "$CONSOLIDATED"
        cat "$PROJECT_DIR/prompts/browser-protocol.md" >> "$CONSOLIDATED"
    fi
fi
```

### 6c. Session Completion (after return)

After `claude -p` returns, update the session:

```bash
# Update session with results
python -c "
import sqlite3, datetime
db = sqlite3.connect('$DB_PATH')
ts = datetime.datetime.utcnow().isoformat()
started = db.execute('SELECT started_at FROM sessions WHERE session_id = ?', ('$SESSION_ID',)).fetchone()[0]
started_dt = datetime.datetime.fromisoformat(started)
ended_dt = datetime.datetime.fromisoformat(ts)
duration = (ended_dt - started_dt).total_seconds()
success = 1 if $EXIT_CODE == 0 else 0
status = 'completed' if success else 'failed'
db.execute('UPDATE sessions SET status = ?, completed_at = ?, duration_seconds = ?, success = ?, output_snapshot = ?, error_message = ? WHERE session_id = ?',
    (status, ts, duration, success, '''$OUTPUT''', '''$ERROR''' if not success else None, '$SESSION_ID'))
db.commit()
db.close()
"
```

---

## 7. Schema Changes Summary

### New Tables (3)

| Table | Purpose |
|-------|---------|
| `sessions` | Records every agent dispatch lifecycle |
| `session_recordings` | Step-by-step browser action log per session |
| `credentials` | Preconfigured site login credentials |

### Modified Files

| File | Change |
|------|--------|
| `scripts/db-init.py` | Add 3 new tables to schema creation |
| `scripts/dispatch-agent.sh` | Add session creation/completion, conditional browser protocol |
| `prompts/browser-protocol.md` | New protocol file (browser Workers only) |

### No Changes To

- Existing agent prompts (director, planner, librarian, researcher, executor, auditor, improvement)
- Existing protocols (db-access, reporting, memory, evaluation)
- Existing tables (agents, tasks, events, memory_long, memory_short, skill_registry, skill_invocations, cron_schedule, work_releases, auto_release_rules, improvement_log, config)

---

## 8. Future: Puppeteer/Playwright Extensibility

The design is structured so the browser execution engine can be swapped without changing Worker prompts or skill templates.

**When ready to add Puppeteer:**

1. Add `execution_engine` column to `credentials` table — values: `chrome_extension` (default), `puppeteer`, `playwright`
2. Build an MCP server wrapping Puppeteer (Approach C from brainstorming)
3. Update `prompts/browser-protocol.md` to check execution engine and route commands accordingly
4. Worker prompts and skill templates remain unchanged — they use the same action vocabulary (`navigate`, `click`, `fill`, etc.)
5. The MCP server translates these actions to the appropriate Puppeteer/Playwright API calls

**Benefits of this path:**
- Headless execution for background tasks
- Better parallelism (no Chrome Extension bottleneck)
- Programmatic DOM control for complex interactions
- Easy integration with CI/CD pipelines
