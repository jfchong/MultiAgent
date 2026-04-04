# Reporting Protocol

When you complete a task, follow this reporting sequence.

## 1. Write Output Data

Store your results in the task's output_data field as a JSON envelope:

```bash
python -c "
import sqlite3, json
from datetime import datetime, timezone
db = sqlite3.connect('C:/Users/jfcho/Desktop/CoWork/MultiAgent/ultra.db')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
output = json.dumps({
    'type': '{result_type}',
    'agent': '{your_agent_id}',
    'task_id': '{task_id}',
    'timestamp': ts,
    'payload': {
        # Your actual results here
    },
    'metadata': {
        'confidence': 0.9,
        'toolkits_used': [],
        'notes': ''
    }
})
db.execute('UPDATE tasks SET output_data = ?, status = ?, completed_at = ?, updated_at = ? WHERE task_id = ?',
    (output, 'completed', ts, ts, '{task_id}'))
db.commit()
db.close()
"
```

## 2. Log Completion Event

```bash
python -c "
import sqlite3, uuid, json
from datetime import datetime, timezone
db = sqlite3.connect('C:/Users/jfcho/Desktop/CoWork/MultiAgent/ultra.db')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('INSERT INTO events (event_id, event_type, agent_id, task_id, data_json, created_at) VALUES (?, ?, ?, ?, ?, ?)',
    (str(uuid.uuid4()), 'task_completed', '{your_agent_id}', '{task_id}', '{}', ts))
db.commit()
db.close()
"
```

## 3. Update Agent Counters

```bash
python -c "
import sqlite3
from datetime import datetime, timezone
db = sqlite3.connect('C:/Users/jfcho/Desktop/CoWork/MultiAgent/ultra.db')
ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
db.execute('UPDATE agents SET run_count = run_count + 1, last_run_at = ?, updated_at = ?, status = ? WHERE agent_id = ?',
    (ts, ts, 'idle', '{your_agent_id}'))
db.commit()
db.close()
"
```

## 4. Print Final Output

At the end of your session, print a JSON summary to stdout so the caller can parse it:

```json
{
  "status": "completed",
  "task_id": "...",
  "summary": "Brief description of what was accomplished",
  "subtasks_created": ["task_id_1", "task_id_2"],
  "errors": []
}
```

## On Failure

If you encounter an unrecoverable error:

1. Set task status to 'failed' with error_message
2. Log a 'task_failed' event
3. Set agent status to 'error'
4. Print error summary to stdout
