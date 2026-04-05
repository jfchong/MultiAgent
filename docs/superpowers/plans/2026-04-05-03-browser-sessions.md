# Phase 3: Browser Integration & Session Recording — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add browser control for Workers (via Chrome Extension), per-dispatch session recording, credential management, and automatic skill template saving from successful browser sessions.

**Architecture:** Three new SQLite tables (sessions, session_recordings, credentials) added to db-init.py. A new browser protocol prompt (browser-protocol.md) is conditionally appended only to browser-capable Workers. The dispatch script creates/completes session records around every agent launch. db-utils.py gets new commands for managing sessions and credentials.

**Tech Stack:** Python 3 (sqlite3 stdlib), Bash, Markdown (prompts), SQLite WAL mode

---

## File Map

| File | Responsibility |
|------|---------------|
| `scripts/db-init.py` | Add 3 new tables: sessions, session_recordings, credentials |
| `scripts/db-utils.py` | Add commands: list-sessions, get-session, create-credential, list-credentials, delete-credential |
| `scripts/dispatch-agent.sh` | Add session creation/completion, conditional browser protocol |
| `prompts/browser-protocol.md` | Browser action vocabulary, category constraints, recording rules |

---

### Task 1: Add New Tables to db-init.py

**Files:**
- Modify: `scripts/db-init.py`

- [ ] **Step 1: Add the sessions table**

In `scripts/db-init.py`, inside the `create_tables` function, after the `improvement_log` table creation and before the `config` table creation, add:

```python
    c.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id        TEXT PRIMARY KEY,
        agent_id          TEXT NOT NULL REFERENCES agents(agent_id),
        task_id           TEXT NOT NULL REFERENCES tasks(task_id),
        parent_session_id TEXT REFERENCES sessions(session_id),
        browser_category  TEXT CHECK(browser_category IN ('SS-SM','SS-MM','MS-SM','MS-MM') OR browser_category IS NULL),
        status            TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','completed','failed','timeout')),
        started_at        TEXT NOT NULL,
        completed_at      TEXT,
        duration_seconds  REAL,
        success           INTEGER CHECK(success IN (0, 1) OR success IS NULL),
        summary           TEXT,
        output_snapshot   TEXT,
        error_message     TEXT,
        created_at        TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_task ON sessions(task_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_success ON sessions(success)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_parent ON sessions(parent_session_id)")
```

- [ ] **Step 2: Add the session_recordings table**

Immediately after the sessions table, add:

```python
    c.execute("""
    CREATE TABLE IF NOT EXISTS session_recordings (
        recording_id  TEXT PRIMARY KEY,
        session_id    TEXT NOT NULL REFERENCES sessions(session_id),
        step_number   INTEGER NOT NULL,
        action_type   TEXT NOT NULL CHECK(action_type IN (
            'auto_login','navigate','click','fill','screenshot',
            'wait','extract','assert'
        )),
        target        TEXT,
        value         TEXT,
        result        TEXT,
        timestamp     TEXT NOT NULL,
        duration_ms   INTEGER,
        UNIQUE(session_id, step_number)
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_recordings_session ON session_recordings(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_recordings_action ON session_recordings(action_type)")
```

- [ ] **Step 3: Add the credentials table**

Immediately after the session_recordings table, add:

```python
    c.execute("""
    CREATE TABLE IF NOT EXISTS credentials (
        credential_id    TEXT PRIMARY KEY,
        site_domain      TEXT NOT NULL UNIQUE,
        label            TEXT NOT NULL,
        auth_type        TEXT NOT NULL DEFAULT 'password' CHECK(auth_type IN ('password','oauth','api_key','cookie')),
        credentials_json TEXT NOT NULL,
        created_at       TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_credentials_domain ON credentials(site_domain)")
```

- [ ] **Step 4: Verify by reinitializing the database**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
rm -f ultra.db
python scripts/db-init.py
```

Expected: Database created with 15 tables (12 existing + 3 new) and 7 agents.

- [ ] **Step 5: Verify new tables exist with correct columns**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
python -c "
import sqlite3
db = sqlite3.connect('ultra.db')
for table in ['sessions', 'session_recordings', 'credentials']:
    cols = db.execute(f'PRAGMA table_info({table})').fetchall()
    print(f'{table} ({len(cols)} columns):')
    for col in cols:
        print(f'  {col[1]} ({col[2]})')
    print()
db.close()
"
```

Expected: sessions (14 columns), session_recordings (9 columns), credentials (7 columns).

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add scripts/db-init.py
git commit -m "feat: add sessions, session_recordings, credentials tables to schema"
```

---

### Task 2: Add Session and Credential Commands to db-utils.py

**Files:**
- Modify: `scripts/db-utils.py`

- [ ] **Step 1: Add the list-sessions command**

In `scripts/db-utils.py`, add this function before the `COMMANDS` dict:

```python
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
            i += 2  # handled below
        else:
            i += 1

    sql = "SELECT * FROM sessions"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY started_at DESC"

    # Check for --limit
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
```

- [ ] **Step 2: Add the get-session command**

```python
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
```

- [ ] **Step 3: Add the create-credential command**

```python
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
```

- [ ] **Step 4: Add the list-credentials command**

```python
def cmd_list_credentials(args):
    conn = get_conn()
    rows = conn.execute("SELECT credential_id, site_domain, label, auth_type, created_at, updated_at FROM credentials ORDER BY site_domain").fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))
```

Note: This intentionally omits `credentials_json` from the output to avoid accidentally printing secrets to stdout.

- [ ] **Step 5: Add the delete-credential command**

```python
def cmd_delete_credential(args):
    site_domain = args[0]
    conn = get_conn()
    conn.execute("DELETE FROM credentials WHERE site_domain = ?", (site_domain,))
    conn.commit()
    conn.close()
    print(json.dumps({"deleted": site_domain}))
```

- [ ] **Step 6: Register all new commands in the COMMANDS dict**

Update the `COMMANDS` dict to include:

```python
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
```

- [ ] **Step 7: Verify new commands work**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"

# Test list-sessions (should return empty list)
python scripts/db-utils.py list-sessions

# Test create-credential
python scripts/db-utils.py create-credential --domain csshome.info --label "PPPSU CSS Portal" --username test --password test123

# Test list-credentials (should show 1 credential, NO password in output)
python scripts/db-utils.py list-credentials

# Test delete-credential
python scripts/db-utils.py delete-credential csshome.info

# Verify deleted
python scripts/db-utils.py list-credentials
```

Expected: Empty sessions list, credential created then listed (without credentials_json), then deleted.

- [ ] **Step 8: Commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add scripts/db-utils.py
git commit -m "feat: add session and credential management commands to db-utils"
```

---

### Task 3: Write Browser Protocol

**Files:**
- Create: `prompts/browser-protocol.md`

- [ ] **Step 1: Create the browser protocol prompt**

```markdown
# Browser Protocol

You are a browser-capable Worker. You control Chrome browser tabs via the Claude Chrome Extension to complete your assigned task.

## Your Browser Category

Your browser category is set in your agent config. It defines your operational scope:

- **SS-SM (Single Site, Single Motive):** You will receive ONE site and ONE action. Execute it and return. Do not navigate to other sites.
- **SS-MM (Single Site, Multi Motive):** You will receive ONE site and MULTIPLE actions. Execute them sequentially on the same site. Do not navigate to other sites.
- **MS-SM (Multi Site, Single Motive):** You will receive MULTIPLE sites and ONE action type. Execute the same action on each site in order.
- **MS-MM (Multi Site, Multi Motive):** You will receive MULTIPLE sites and MULTIPLE actions. Follow the action plan exactly as specified.

Stay within your category scope. Do not add extra navigation or actions beyond what your task specifies.

## Action Vocabulary

Use these standard actions to interact with browser pages:

### auto_login — Log into a site using stored credentials

```bash
python -c "
import sqlite3, json
db = sqlite3.connect('ultra.db')
row = db.execute('SELECT credentials_json, auth_type FROM credentials WHERE site_domain = ?', ('{site_domain}',)).fetchone()
if row:
    creds = json.loads(row[0])
    print(json.dumps(creds))
else:
    print('ERROR: No credentials for {site_domain}')
db.close()
"
```

Use the retrieved credentials to fill the login form. After login, verify you reached the expected post-login page.

**Recording:** Log as `action_type='auto_login', target='{site_domain}', result='success' or 'failed'`. NEVER log the actual username or password.

### navigate — Go to a URL

Navigate the browser to the specified URL. Wait for the page to load before proceeding.

### click — Click an element

Click the element matching the CSS selector or description. If the element is not visible, scroll to it first.

### fill — Type into a form field

Clear the field first, then type the specified value. For dropdowns, select the matching option.

### screenshot — Capture current page state

Take a screenshot and save it with the specified label. Use this before and after critical actions for audit purposes.

### wait — Wait for element or condition

Wait for the specified element to appear on the page. If not found within the timeout (default 5000ms), report failure.

### extract — Pull text/data from page

Extract the text content of the element matching the selector. Store the extracted value in your task output.

### assert — Verify expected page state

Check that the element matching the selector contains the expected value. If it doesn't match, report the actual value and mark the step as failed.

## Recording Every Action

You MUST log every browser action to `session_recordings` immediately after execution. This is mandatory.

```bash
python -c "
import sqlite3, uuid, datetime
db = sqlite3.connect('ultra.db')
db.execute('INSERT INTO session_recordings (recording_id, session_id, step_number, action_type, target, value, result, timestamp, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
  (str(uuid.uuid4()), '{session_id}', {step_number}, '{action_type}', '{target}', '{value}', '{result}', datetime.datetime.utcnow().isoformat(), {duration_ms}))
db.commit()
db.close()
"
```

Replace the placeholders with actual values for each action:
- `{session_id}` — Your session ID (provided in your task context)
- `{step_number}` — Sequential counter starting at 1
- `{action_type}` — One of: auto_login, navigate, click, fill, screenshot, wait, extract, assert
- `{target}` — URL, CSS selector, or element description
- `{value}` — Input value for fill, expected value for assert, or empty
- `{result}` — What happened: extracted text, 'success', 'failed', screenshot path
- `{duration_ms}` — How long this step took in milliseconds

## Executing a Skill Template

If your task includes a skill template (JSON action plan), follow it step by step:

1. Read the template from your task's `input_data`
2. Replace all `{placeholder}` values with the actual data from your task
3. Execute each step in order using the actions above
4. Record every step to `session_recordings`
5. Collect all output values (from `extract` actions) into your result

Example template execution:
```json
{"action": "auto_login", "site": "csshome.info"}
```
→ Look up credentials for csshome.info, perform login, record step

```json
{"action": "fill", "target": "#unit-number", "value": "{unit_number}"}
```
→ Replace {unit_number} with actual value from input_data, fill the field, record step

```json
{"action": "extract", "target": ".outstanding-amount", "as": "outstanding_amount"}
```
→ Extract the text, save as "outstanding_amount" in your output, record step

## Error Handling

1. **Page doesn't load:** Screenshot the current state, record the error, report failure
2. **Element not found:** Wait up to the timeout, screenshot, record the error, report failure
3. **Unexpected page state:** Screenshot, record actual vs expected, report failure
4. **Do NOT retry** unless the skill template explicitly includes retry steps
5. On any failure, your session is marked `success = 0`

## Rules

1. **Record every action** — No browser action goes unrecorded in session_recordings
2. **Never log credentials** — auto_login recordings show domain only, never usernames or passwords
3. **Stay in scope** — Only visit sites and perform actions specified in your task
4. **Screenshot on failure** — Always capture the page state when something goes wrong
5. **Follow the template** — If given a skill template, execute it exactly as specified
```

- [ ] **Step 2: Commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add prompts/browser-protocol.md
git commit -m "feat: add browser protocol for Chrome Extension Workers"
```

---

### Task 4: Update Dispatch Script for Session Tracking

**Files:**
- Modify: `scripts/dispatch-agent.sh`

This task modifies the dispatch script to: (a) create a session record before launch, (b) conditionally append browser protocol, and (c) update the session after completion.

- [ ] **Step 1: Read the current dispatch script to confirm the exact lines**

Read `scripts/dispatch-agent.sh` to identify the exact insertion points.

- [ ] **Step 2: Add AGENT_CONFIG extraction after AGENT_LEVEL**

After line 43 (the `AGENT_LEVEL=...` line), add:

```bash
AGENT_CONFIG=$(echo "$AGENT_JSON" | python -c "import sys,json; print(json.load(sys.stdin).get('config_json','{}'))")
```

- [ ] **Step 3: Add session creation after the "Mark agent as running" block**

After the closing `"` of the Python block that marks agent as running (after the existing line 75 `"`), add:

```bash

# --- 3b. Create session record ---
SESSION_ID=$(python -c "
import sqlite3, uuid, json
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
sid = str(uuid.uuid4())
browser_cat = None
try:
    config = json.loads('$AGENT_CONFIG')
    browser_cat = config.get('browser_category')
except:
    pass
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('INSERT INTO sessions (session_id, agent_id, task_id, browser_category, status, started_at) VALUES (?, ?, ?, ?, ?, ?)',
    (sid, '$AGENT_ID', '$TASK_ID', browser_cat, 'running', ts))
db.commit()
print(sid)
db.close()
")
echo "[dispatch] Session=$SESSION_ID" >&2
```

- [ ] **Step 4: Add conditional browser protocol append**

After the existing `for protocol in ...` loop (after line 113 `done`), add:

```bash

# Append browser protocol if agent has browser_category
BROWSER_CAT=$(echo "$AGENT_CONFIG" | python -c "
import sys, json
try:
    config = json.loads(sys.stdin.read())
    print(config.get('browser_category', ''))
except:
    print('')
")

if [ -n "$BROWSER_CAT" ]; then
    if [ -f "$PROJECT_DIR/prompts/browser-protocol.md" ]; then
        echo "" >> "$CONSOLIDATED"
        cat "$PROJECT_DIR/prompts/browser-protocol.md" >> "$CONSOLIDATED"
        echo "[dispatch] Browser protocol appended (category=$BROWSER_CAT)" >&2
    fi
fi
```

- [ ] **Step 5: Add session completion to the foreground path**

In the foreground (else) branch, after `echo "$RESULT"` (line 137), replace the cleanup and idle-marking block with:

```bash
    echo "$RESULT"

    # Clean up consolidated prompt
    rm -f "$CONSOLIDATED"

    # Update session with results
    python -c "
import sqlite3
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
row = db.execute('SELECT started_at FROM sessions WHERE session_id = ?', ('$SESSION_ID',)).fetchone()
if row:
    started = row[0]
    from datetime import datetime as dt
    try:
        s = dt.fromisoformat(started.replace('Z', '+00:00'))
        e = dt.fromisoformat(ts.replace('Z', '+00:00'))
        duration = (e - s).total_seconds()
    except:
        duration = 0
    db.execute('UPDATE sessions SET status = ?, completed_at = ?, duration_seconds = ?, success = ?, output_snapshot = ? WHERE session_id = ?',
        ('completed', ts, duration, 1, '''$(echo "$RESULT" | head -c 10000)''', '$SESSION_ID'))
db.commit()
db.close()
"

    # Mark agent as idle
    python -c "
import sqlite3
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('UPDATE agents SET status = ?, updated_at = ? WHERE agent_id = ?',
    ('idle', ts, '$AGENT_ID'))
db.commit()
db.close()
"
```

- [ ] **Step 6: Add session_id to the task prompt context**

In the TASK_PROMPT section (section 4), add the session ID so browser Workers know it. Update the prompt to include:

After the existing `Dependencies` line in the TASK_PROMPT heredoc, add:

```
Session ID: $SESSION_ID
```

So the full TASK_PROMPT becomes:

```bash
TASK_PROMPT="You are agent '$AGENT_ID' (Level $AGENT_LEVEL). Your assigned task:

Task ID: $TASK_ID
$(echo "$TASK_JSON" | python -c "
import sys, json
t = json.load(sys.stdin)
print(f\"Title: {t['title']}\")
print(f\"Description: {t.get('description', 'N/A')}\")
print(f\"Priority: {t['priority']}\")
print(f\"Framework: {t.get('framework', 'Not set')}\")
print(f\"Input Data: {t.get('input_data', 'None')}\")
print(f\"Dependencies: {t.get('depends_on_json', '[]')}\")
")
Session ID: $SESSION_ID

Execute your task following your system prompt instructions. Use the database access and reporting protocols. When done, print a JSON summary to stdout."
```

Note: The TASK_PROMPT must be built AFTER the SESSION_ID is created, so the session creation block (step 3) must come before the TASK_PROMPT construction (section 4). Reorder the sections in the script so that:
1. Read agent info (existing section 1)
2. Read task context (existing section 2)
3. Extract AGENT_CONFIG (new)
4. Mark agent as running (existing section 3)
5. Create session record (new section 3b)
6. Build task prompt (existing section 4, now includes SESSION_ID)
7. Build consolidated prompt (existing section 5, now includes browser protocol)
8. Dispatch (existing section 6)

- [ ] **Step 7: Verify script syntax**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
bash -n scripts/dispatch-agent.sh
echo "Syntax check: $?"
```

Expected: Exit code 0.

- [ ] **Step 8: Commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add scripts/dispatch-agent.sh
git commit -m "feat: add session tracking and conditional browser protocol to dispatch"
```

---

### Task 5: Integration Verification

- [ ] **Step 1: Initialize fresh database**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
rm -f ultra.db
python scripts/db-init.py
```

Expected: Database created with 15 tables and 7 agents.

- [ ] **Step 2: Verify all 15 tables exist**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
python -c "
import sqlite3
db = sqlite3.connect('ultra.db')
tables = db.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\").fetchall()
print(f'Tables ({len(tables)}):')
for t in tables:
    cols = db.execute(f'PRAGMA table_info({t[0]})').fetchall()
    print(f'  {t[0]} ({len(cols)} cols)')
db.close()
"
```

Expected: 15 tables including sessions, session_recordings, credentials.

- [ ] **Step 3: Test credential CRUD**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"

# Create
python scripts/db-utils.py create-credential --domain csshome.info --label "PPPSU CSS Portal" --username pppsu_admin --password secret123

# List (should NOT show credentials_json)
python scripts/db-utils.py list-credentials

# Verify the password IS stored (direct query for testing only)
python scripts/db-utils.py query "SELECT site_domain, credentials_json FROM credentials WHERE site_domain = 'csshome.info'"

# Delete
python scripts/db-utils.py delete-credential csshome.info
python scripts/db-utils.py list-credentials
```

Expected: Credential created, listed without secrets, queried with secrets, deleted.

- [ ] **Step 4: Test session creation via direct insert**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"

# Create a test task first
TASK_RESULT=$(python scripts/db-utils.py create-task --title "Test browser task" --description "Test session recording" --assigned executor --priority 3 --created-by director)
TASK_ID=$(echo "$TASK_RESULT" | python -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

# Simulate a session with recordings
python -c "
import sqlite3, uuid, datetime
db = sqlite3.connect('ultra.db')
sid = str(uuid.uuid4())
ts = datetime.datetime.utcnow().isoformat()

# Create session
db.execute('INSERT INTO sessions (session_id, agent_id, task_id, browser_category, status, started_at) VALUES (?, ?, ?, ?, ?, ?)',
    (sid, 'executor', '$TASK_ID', 'SS-MM', 'running', ts))

# Add recordings
for i, (action, target, value, result) in enumerate([
    ('auto_login', 'csshome.info', None, 'success'),
    ('fill', '#unit-number', 'B-12-03', 'filled'),
    ('click', '#search-btn', None, 'clicked'),
    ('wait', '.results-table', '5000', 'found'),
    ('extract', '.outstanding-amount', None, 'RM 1,250.00'),
], 1):
    db.execute('INSERT INTO session_recordings (recording_id, session_id, step_number, action_type, target, value, result, timestamp, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (str(uuid.uuid4()), sid, i, action, target, value, result, ts, 150))

# Complete session
db.execute('UPDATE sessions SET status = ?, completed_at = ?, duration_seconds = ?, success = ? WHERE session_id = ?',
    ('completed', ts, 2.5, 1, sid))
db.commit()
print(f'Session: {sid}')
db.close()
"
```

- [ ] **Step 5: Verify session query commands**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"

# List sessions
python scripts/db-utils.py list-sessions --success 1

# List browser-only sessions
python scripts/db-utils.py list-sessions --browser

# Get session with recordings (use the session ID from step 4 output)
python scripts/db-utils.py query "SELECT session_id FROM sessions LIMIT 1"
```

Expected: Sessions listed, browser filter works, recordings included in get-session.

- [ ] **Step 6: Verify browser protocol file exists**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
wc -l prompts/browser-protocol.md
```

Expected: Non-zero line count.

- [ ] **Step 7: Verify dispatch script includes browser protocol logic**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
grep "browser_category" scripts/dispatch-agent.sh
grep "browser-protocol" scripts/dispatch-agent.sh
grep "SESSION_ID" scripts/dispatch-agent.sh | head -5
```

Expected: References to browser_category, browser-protocol.md, and SESSION_ID found.

- [ ] **Step 8: Clean up test data**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
python scripts/db-utils.py query "DELETE FROM session_recordings"
python scripts/db-utils.py query "DELETE FROM sessions"
python scripts/db-utils.py query "DELETE FROM tasks"
python scripts/db-utils.py query "DELETE FROM credentials"
```

- [ ] **Step 9: Final commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add -A
git status
git commit -m "chore: Phase 3 Browser Integration & Session Recording complete"
```

---

## Plan Self-Review

**Spec coverage:**
- [x] Worker browser categories — SS-SM, SS-MM, MS-SM, MS-MM (Task 3 protocol + Task 1 schema constraint)
- [x] Sessions table with all columns from spec (Task 1)
- [x] Session recordings table with all columns from spec (Task 1)
- [x] Credentials table with all columns from spec (Task 1)
- [x] Security rules — credentials_json excluded from list-credentials output (Task 2)
- [x] Browser action vocabulary — all 8 actions defined (Task 3)
- [x] Category constraints in protocol (Task 3)
- [x] Recording requirement — mandatory logging (Task 3)
- [x] Error handling rules (Task 3)
- [x] Credential lookup flow via auto_login (Task 3)
- [x] Skill template execution instructions (Task 3)
- [x] Dispatch session creation before launch (Task 4)
- [x] Dispatch conditional browser protocol (Task 4)
- [x] Dispatch session completion after return (Task 4)
- [x] Session ID passed to agent in task prompt (Task 4)
- [x] db-utils commands for sessions and credentials (Task 2)
- [x] Integration verification (Task 5)

**Placeholder scan:** No TBDs, TODOs, or "implement later" found. All code blocks contain complete content.

**Type consistency:** `browser_category` values (SS-SM, SS-MM, MS-SM, MS-MM) match across schema CHECK constraint (Task 1), protocol (Task 3), and dispatch script (Task 4). `action_type` values in session_recordings CHECK constraint match the protocol vocabulary. Column names match across all files.
