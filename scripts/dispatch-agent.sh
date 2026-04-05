#!/usr/bin/env bash
# dispatch-agent.sh — Dispatch a Claude CLI agent with layered prompts
#
# Usage:
#   bash scripts/dispatch-agent.sh <agent_id> <task_id> [--model sonnet] [--background]
#
# The script:
# 1. Reads the agent's prompt_file from SQLite
# 2. Reads the task context from SQLite
# 3. Builds a consolidated system prompt (base + protocols)
# 4. Dispatches via `claude -p` with --append-system-prompt-file
# 5. Captures output and updates the DB

set -euo pipefail

PROJECT_DIR="C:/Users/jfcho/Desktop/CoWork/MultiAgent"
DB_PATH="$PROJECT_DIR/ultra.db"

AGENT_ID="${1:?Usage: dispatch-agent.sh <agent_id> <task_id>}"
TASK_ID="${2:?Usage: dispatch-agent.sh <agent_id> <task_id>}"
MODEL="${3:-sonnet}"
BACKGROUND="${4:-}"

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
for protocol in db-access-protocol.md reporting-protocol.md memory-protocol.md evaluation-protocol.md; do
    if [ -f "$PROJECT_DIR/prompts/$protocol" ]; then
        echo "" >> "$CONSOLIDATED"
        cat "$PROJECT_DIR/prompts/$protocol" >> "$CONSOLIDATED"
    fi
done

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
    echo "{\"pid\": $PID, \"agent_id\": \"$AGENT_ID\", \"task_id\": \"$TASK_ID\"}"
else
    RESULT=$($CLAUDE_CMD "$TASK_PROMPT" 2>"$PROJECT_DIR/logs/$AGENT_ID-$TASK_ID.stderr")
    echo "$RESULT"

    # Clean up consolidated prompt
    rm -f "$CONSOLIDATED"

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
