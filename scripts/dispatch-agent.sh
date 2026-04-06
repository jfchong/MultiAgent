#!/usr/bin/env bash
# dispatch-agent.sh — Dispatch a Claude CLI agent with layered prompts
#
# Usage:
#   bash scripts/dispatch-agent.sh <agent_id> <task_id> [--model sonnet] [--background]
#
# The script:
# 1. Reads the agent's prompt_file and config from SQLite
# 2. Reads the task context from SQLite
# 3. Creates a session record for tracking
# 4. Builds a consolidated system prompt (base + protocols + browser if needed)
# 5. Dispatches via `claude -p` with --append-system-prompt-file
# 6. Updates session and agent status on completion

set -euo pipefail

PROJECT_DIR="C:/Users/jfcho/Desktop/CoWork/MultiAgent"
DB_PATH="$PROJECT_DIR/ultra.db"

AGENT_ID="${1:?Usage: dispatch-agent.sh <agent_id> <task_id>}"
TASK_ID="${2:?Usage: dispatch-agent.sh <agent_id> <task_id>}"
MODEL="${3:-sonnet}"
BACKGROUND="${4:-}"

# --- Error recovery trap ---
# SESSION_ID and CONSOLIDATED are set later; the trap references them via variables
# that are guaranteed to exist (initialized empty) before any command that could fail.
SESSION_ID=""
CONSOLIDATED=""

cleanup_on_error() {
    local exit_code=$?
    echo "[dispatch] ERROR: exit_code=$exit_code — running cleanup" >&2

    # Update session to failed (only if SESSION_ID has been set)
    if [ -n "$SESSION_ID" ]; then
        python -c "
import sqlite3
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('''UPDATE sessions
              SET status = 'failed', completed_at = ?, success = 0
              WHERE session_id = ?''', (ts, '$SESSION_ID'))
db.commit()
db.close()
" 2>/dev/null || true
    fi

    # Update agent to error, increment error_count
    python -c "
import sqlite3
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('''UPDATE agents
              SET status = 'error', error_count = COALESCE(error_count, 0) + 1, updated_at = ?
              WHERE agent_id = ?''', (ts, '$AGENT_ID'))
db.commit()
db.close()
" 2>/dev/null || true

    # Check task retry_count vs max_retries; reset to pending if retries remain
    python -c "
import sqlite3
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
db.row_factory = sqlite3.Row
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
row = db.execute('SELECT retry_count, max_retries FROM tasks WHERE task_id = ?', ('$TASK_ID',)).fetchone()
if row:
    retry_count = row['retry_count'] or 0
    max_retries = row['max_retries'] or 0
    if retry_count < max_retries:
        db.execute('''UPDATE tasks
                      SET status = 'pending', retry_count = ?, updated_at = ?
                      WHERE task_id = ?''', (retry_count + 1, ts, '$TASK_ID'))
        print('[dispatch] Task reset to pending (retry ' + str(retry_count + 1) + '/' + str(max_retries) + ')', flush=True)
    else:
        db.execute('''UPDATE tasks SET status = 'failed', updated_at = ? WHERE task_id = ?''',
                   (ts, '$TASK_ID'))
        print('[dispatch] Task marked failed (no retries remaining)', flush=True)
    db.commit()
db.close()
" 2>/dev/null || true

    # Clean up consolidated prompt file
    if [ -n "$CONSOLIDATED" ] && [ -f "$CONSOLIDATED" ]; then
        rm -f "$CONSOLIDATED"
    fi
}

trap cleanup_on_error ERR

# --- 1. Read agent info from DB ---
AGENT_JSON=$(python -c "
import sqlite3, json
db = sqlite3.connect('$DB_PATH')
db.row_factory = sqlite3.Row
row = db.execute('SELECT * FROM agents WHERE agent_id = ?', ('$AGENT_ID',)).fetchone()
if row:
    print(json.dumps(dict(row)))
else:
    print('null')
db.close()
")

if [ "$AGENT_JSON" = "null" ]; then
    echo "Error: Agent '$AGENT_ID' not found" >&2
    exit 1
fi

PROMPT_FILE=$(echo "$AGENT_JSON" | python -c "import sys,json; print(json.load(sys.stdin).get('prompt_file',''))")
AGENT_LEVEL=$(echo "$AGENT_JSON" | python -c "import sys,json; print(json.load(sys.stdin).get('level',1))")
AGENT_CONFIG=$(echo "$AGENT_JSON" | python -c "import sys,json; print(json.load(sys.stdin).get('config_json','{}'))")

# --- 2. Read task context from DB ---
TASK_JSON=$(python -c "
import sqlite3, json
db = sqlite3.connect('$DB_PATH')
db.row_factory = sqlite3.Row
row = db.execute('SELECT * FROM tasks WHERE task_id = ?', ('$TASK_ID',)).fetchone()
if row:
    print(json.dumps(dict(row)))
else:
    print('null')
db.close()
")

if [ "$TASK_JSON" = "null" ]; then
    echo "Error: Task '$TASK_ID' not found" >&2
    exit 1
fi

# --- 3. Mark agent as running ---
python -c "
import sqlite3
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('UPDATE agents SET status = ?, last_run_at = ?, updated_at = ? WHERE agent_id = ?',
    ('running', ts, ts, '$AGENT_ID'))
db.execute('UPDATE tasks SET status = ?, started_at = ?, updated_at = ? WHERE task_id = ? AND status IN (?, ?)',
    ('in_progress', ts, ts, '$TASK_ID', 'assigned', 'awaiting_release'))
db.commit()
db.close()
"

# --- 3b. Create session record ---
SESSION_ID=$(python -c "
import sqlite3, uuid, json
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
sid = str(uuid.uuid4())
browser_cat = None
try:
    config = json.loads('''$AGENT_CONFIG''')
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

# --- 4. Build the prompt ---
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

# --- 5. Build consolidated prompt file ---
CONSOLIDATED="$PROJECT_DIR/prompts/.dispatch-$AGENT_ID-$TASK_ID.md"

# Start with the base agent prompt
if [ -f "$PROJECT_DIR/$PROMPT_FILE" ]; then
    cat "$PROJECT_DIR/$PROMPT_FILE" > "$CONSOLIDATED"
else
    echo "Warning: Prompt file '$PROMPT_FILE' not found, using empty base" >&2
    echo "# Agent: $AGENT_ID" > "$CONSOLIDATED"
fi

# Append protocol prompts
echo "" >> "$CONSOLIDATED"
echo "---" >> "$CONSOLIDATED"
for protocol in db-access-protocol.md reporting-protocol.md memory-protocol.md evaluation-protocol.md skill-protocol.md; do
    if [ -f "$PROJECT_DIR/prompts/$protocol" ]; then
        echo "" >> "$CONSOLIDATED"
        cat "$PROJECT_DIR/prompts/$protocol" >> "$CONSOLIDATED"
    fi
done

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

# --- 6. Dispatch ---
echo "[dispatch] Agent=$AGENT_ID Task=$TASK_ID Model=$MODEL" >&2

CLAUDE_CMD="claude -p --model $MODEL --output-format json --dangerously-skip-permissions"
CLAUDE_CMD="$CLAUDE_CMD --append-system-prompt-file $CONSOLIDATED"
CLAUDE_CMD="$CLAUDE_CMD --add-dir $PROJECT_DIR"

if [ "$BACKGROUND" = "--background" ]; then
    $CLAUDE_CMD "$TASK_PROMPT" > "$PROJECT_DIR/logs/$AGENT_ID-$TASK_ID.json" 2>&1 &
    PID=$!
    echo "[dispatch] Background PID=$PID" >&2

    # Store PID for health monitoring
    python -c "
import sqlite3
db = sqlite3.connect('$DB_PATH')
db.execute('UPDATE agents SET session_id = ? WHERE agent_id = ?', ('$PID', '$AGENT_ID'))
db.commit()
db.close()
"

    # --- Watchdog: kill background process if it exceeds configured timeout ---
    TIMEOUT_MINUTES=$(python -c "
import sqlite3
db = sqlite3.connect('$DB_PATH')
try:
    row = db.execute(\"SELECT value FROM config WHERE key = 'stuck_agent_timeout_minutes'\").fetchone()
    print(int(row[0]) if row else 10)
except:
    print(10)
db.close()
" 2>/dev/null || echo 10)
    TIMEOUT_SECONDS=$(( TIMEOUT_MINUTES * 60 ))
    echo "[dispatch] Watchdog set: $TIMEOUT_MINUTES min ($TIMEOUT_SECONDS s) for PID=$PID" >&2
    (
        sleep "$TIMEOUT_SECONDS"
        if kill -0 "$PID" 2>/dev/null; then
            echo "[dispatch] Watchdog: killing timed-out PID=$PID (agent=$AGENT_ID)" >&2
            kill "$PID" 2>/dev/null || true
            # Mark session and agent as failed due to timeout
            python -c "
import sqlite3
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('''UPDATE sessions SET status = 'failed', completed_at = ?, success = 0,
              error_message = 'Watchdog timeout' WHERE session_id = ?''',
           (ts, '$SESSION_ID'))
db.execute('''UPDATE agents SET status = 'error',
              error_count = COALESCE(error_count, 0) + 1, updated_at = ?
              WHERE agent_id = ?''', (ts, '$AGENT_ID'))
db.commit()
db.close()
" 2>/dev/null || true
        fi
    ) &

    echo "{\"pid\": $PID, \"agent_id\": \"$AGENT_ID\", \"task_id\": \"$TASK_ID\", \"session_id\": \"$SESSION_ID\"}"
else
    STDERR_FILE="$PROJECT_DIR/logs/$AGENT_ID-$TASK_ID.stderr"
    RESULT=""
    CLAUDE_EXIT=0
    RESULT=$($CLAUDE_CMD "$TASK_PROMPT" 2>"$STDERR_FILE") || CLAUDE_EXIT=$?

    if [ "$CLAUDE_EXIT" -ne 0 ]; then
        ERROR_MSG=$(head -c 2000 "$STDERR_FILE" 2>/dev/null || echo "unknown error")
        echo "[dispatch] claude -p failed with exit $CLAUDE_EXIT: $ERROR_MSG" >&2

        # Write error to session
        python -c "
import sqlite3
from datetime import datetime, timezone
db = sqlite3.connect('$DB_PATH')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
error_msg = open('$STDERR_FILE').read(2000) if __import__('os').path.exists('$STDERR_FILE') else 'claude exit $CLAUDE_EXIT'
db.execute('''UPDATE sessions SET status = 'failed', completed_at = ?, success = 0,
              error_message = ? WHERE session_id = ?''',
           (ts, error_msg, '$SESSION_ID'))
db.commit()
db.close()
" 2>/dev/null || true

        # Clean up and let ERR trap handle agent/task updates
        rm -f "$CONSOLIDATED"
        exit "$CLAUDE_EXIT"
    fi

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
    try:
        s = datetime.fromisoformat(started.replace('Z', '+00:00'))
        e = datetime.fromisoformat(ts.replace('Z', '+00:00'))
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
fi
