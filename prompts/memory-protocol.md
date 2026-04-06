# Memory Protocol

You have access to two memory systems. Use them to retain knowledge across tasks and sessions.

## Long-Term Memory (Persistent)

Long-term memories persist across sessions and are shared system-wide. Use them for facts, patterns, preferences, and domain knowledge that should be remembered permanently.

### Reading Long-Term Memory

Before starting any task, check if relevant knowledge already exists:

```bash
# Search by subject
python scripts/db-utils.py query "SELECT memory_id, agent_id, category, subject, content, confidence FROM memory_long WHERE subject LIKE '%keyword%' ORDER BY confidence DESC, updated_at DESC LIMIT 10"

# Search by category
python scripts/db-utils.py query "SELECT memory_id, subject, content, confidence FROM memory_long WHERE category = '{category}' AND agent_id IN ('{your_agent_id}', 'shared') ORDER BY updated_at DESC LIMIT 10"

# Search by content
python scripts/db-utils.py query "SELECT memory_id, subject, content, confidence FROM memory_long WHERE content LIKE '%search_term%' ORDER BY access_count DESC LIMIT 10"

# Get most accessed (most useful) memories
python scripts/db-utils.py query "SELECT memory_id, subject, content, confidence, access_count FROM memory_long ORDER BY access_count DESC LIMIT 10"
```

### Writing Long-Term Memory

Store new knowledge when you discover something valuable:

```bash
python -c "
import sqlite3, json, uuid, datetime
db = sqlite3.connect('ultra.db')
db.execute('INSERT INTO memory_long (memory_id, agent_id, category, subject, content, confidence, source, tags_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
  (str(uuid.uuid4()), '{your_agent_id}', '{category}', '{subject}', '{content}', {confidence}, '{source}', json.dumps({tags}), datetime.datetime.utcnow().isoformat(), datetime.datetime.utcnow().isoformat()))
db.commit()
db.close()
"
```

### When to Store Long-Term Memory

| Store When | Category | Example |
|-----------|----------|---------|
| New fact learned | `fact` | "Allied Group board meets quarterly" |
| User preference discovered | `preference` | "User prefers bullet-point summaries" |
| Successful approach identified | `approach` | "For email tasks, use researcher then executor" |
| Domain knowledge acquired | `domain_knowledge` | "PPPSU uses CSS portal for billing" |
| Entity relationship mapped | `relationship` | "JF Chong is director of Allied Group" |
| Recurring pattern noticed | `pattern` | "Research tasks complete faster with web search" |
| Rule or limit discovered | `constraint` | "Budget reports need CFO approval above $10k" |

### Updating Existing Memory

When you find a memory that needs correction or updating:

```bash
python -c "
import sqlite3, datetime
db = sqlite3.connect('ultra.db')
db.execute('UPDATE memory_long SET content = ?, confidence = ?, updated_at = ? WHERE memory_id = ?',
  ('{updated_content}', {new_confidence}, datetime.datetime.utcnow().isoformat(), '{memory_id}'))
db.commit()
db.close()
"
```

### Incrementing Access Count

When you use a memory, increment its access count so the system knows which memories are most valuable:

```bash
python -c "
import sqlite3, datetime
db = sqlite3.connect('ultra.db')
db.execute('UPDATE memory_long SET access_count = access_count + 1, updated_at = ? WHERE memory_id = ?',
  (datetime.datetime.utcnow().isoformat(), '{memory_id}'))
db.commit()
db.close()
"
```

## Short-Term Memory (Task-Scoped)

Short-term memory is scoped to a single task and is cleared when the task completes. Use it for working data, intermediate results, and task-specific state.

### Reading Short-Term Memory

```bash
# Read all short-term memory for your current task
python scripts/db-utils.py query "SELECT key, value FROM memory_short WHERE task_id = '{task_id}' AND agent_id = '{your_agent_id}' ORDER BY updated_at DESC"

# Read a specific key
python scripts/db-utils.py query "SELECT value FROM memory_short WHERE task_id = '{task_id}' AND agent_id = '{your_agent_id}' AND key = '{key}'"

# Read all agents' short-term memory for this task (for context)
python scripts/db-utils.py query "SELECT agent_id, key, value FROM memory_short WHERE task_id = '{task_id}' ORDER BY agent_id, updated_at DESC"
```

### Writing Short-Term Memory

```bash
python -c "
import sqlite3, json, uuid, datetime
db = sqlite3.connect('ultra.db')
db.execute('INSERT OR REPLACE INTO memory_short (memory_id, task_id, agent_id, key, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
  (str(uuid.uuid4()), '{task_id}', '{your_agent_id}', '{key}', '{value}', datetime.datetime.utcnow().isoformat(), datetime.datetime.utcnow().isoformat()))
db.commit()
db.close()
"
```

### When to Use Short-Term Memory

| Use For | Key Convention | Example |
|---------|---------------|---------|
| Intermediate results | `step_{n}_result` | Partial data from step 2 |
| Working state | `current_state` | "searching for contacts" |
| Decision rationale | `decision_{topic}` | "Chose approach B because..." |
| Accumulated data | `collected_{type}` | List of found email addresses |
| Error context | `error_{step}` | Details of what went wrong |

## Rules

1. **Check before storing** — Search long-term memory first to avoid duplicates
2. **Be specific** — Subjects should be precise, not vague ("Q1 2026 revenue: $2.3M" not "revenue info")
3. **Set confidence honestly** — 1.0 for verified facts, 0.5-0.8 for likely correct, below 0.5 for uncertain
4. **Tag generously** — Tags make memories findable; include agent, task type, domain
5. **Don't over-store** — Only store knowledge that will be useful for future tasks
