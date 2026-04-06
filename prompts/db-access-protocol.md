# Database Access Protocol

You have access to a SQLite database at `C:/Users/jfcho/Desktop/CoWork/MultiAgent/ultra.db`.

## Reading Data

Use `python scripts/db-utils.py` commands via Bash:

```bash
# Get your agent record
python scripts/db-utils.py get-agent {your_agent_id}

# List your assigned tasks
python scripts/db-utils.py list-tasks --status assigned --agent {your_agent_id}

# Get a specific task
python scripts/db-utils.py get-task {task_id}

# Get config value
python scripts/db-utils.py get-config default_namespace

# Run arbitrary read query
python scripts/db-utils.py query "SELECT * FROM memory_long WHERE agent_id = '{your_agent_id}' ORDER BY updated_at DESC LIMIT 10"
```

## Writing Data

Use Python one-liners for writes beyond what db-utils supports:

```bash
python -c "
import sqlite3, uuid, json
from datetime import datetime, timezone
db = sqlite3.connect('C:/Users/jfcho/Desktop/CoWork/MultiAgent/ultra.db')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('''INSERT INTO events (event_id, event_type, agent_id, task_id, data_json, created_at)
VALUES (?, ?, ?, ?, ?, ?)''', (str(uuid.uuid4()), 'task_started', '{agent_id}', '{task_id}', '{}', ts))
db.commit()
db.close()
"
```

## Creating Subtasks

When you need to decompose work:

```bash
python scripts/db-utils.py create-task \
  --title "Subtask title" \
  --description "What needs to be done" \
  --assigned {target_agent_id} \
  --priority 3 \
  --created-by {your_agent_id}
```

Then set the parent_task_id:

```bash
python -c "
import sqlite3
db = sqlite3.connect('C:/Users/jfcho/Desktop/CoWork/MultiAgent/ultra.db')
db.execute('UPDATE tasks SET parent_task_id = ? WHERE task_id = ?', ('{parent_task_id}', '{new_task_id}'))
db.commit()
db.close()
"
```

## Updating Task Status

```bash
python scripts/db-utils.py update-task {task_id} --status in_progress
python scripts/db-utils.py update-task {task_id} --status completed --output-data '{"result": "..."}'
```

## Writing to Work Releases

Before any action that changes external state, park it for approval:

```bash
python -c "
import sqlite3, uuid, json
from datetime import datetime, timezone
db = sqlite3.connect('C:/Users/jfcho/Desktop/CoWork/MultiAgent/ultra.db')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('''INSERT INTO work_releases (release_id, task_id, agent_id, agent_level, title, description, action_type, input_preview, status, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)''',
(str(uuid.uuid4()), '{task_id}', '{agent_id}', {level}, 'What I want to do', 'Detailed description', '{action_type}', '{input_json}', ts))
db.commit()
db.close()
"
```

Then update the task to awaiting_release:

```bash
python scripts/db-utils.py update-task {task_id} --status awaiting_release
```

## Rules

1. Always use parameterized queries (?) for values — never string-format SQL with user data.
2. Always set updated_at when modifying a row.
3. Always log significant actions to the events table.
4. Always commit after writes.
5. Read your assigned tasks FIRST when waking up — don't assume context.
