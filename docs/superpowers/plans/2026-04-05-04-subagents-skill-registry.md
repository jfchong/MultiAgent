# Phase 4: Sub-Agents & Skill Registry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Sub-Agent (L2) and Worker (L3) prompts, a skill protocol teaching agents how to query/save/reuse skills, db-utils commands for skill and invocation management, and end-to-end integration verification of the full 4-level dispatch chain.

**Architecture:** Sub-Agents and Workers are dispatched via the same `dispatch-agent.sh` mechanism as L1 agents. A new skill protocol prompt teaches any agent how to interact with the skill registry. Sub-Agents get the skill protocol to design skills; Workers get the skill protocol + optionally the browser protocol to execute them. db-utils.py gains 5 new commands for skill CRUD and invocation tracking.

**Tech Stack:** Markdown (agent prompts), Python 3 (sqlite3 stdlib), Bash, SQLite WAL mode

---

## File Map

| File | Responsibility |
|------|---------------|
| `agents/sub-agent.md` | Sub-Agent (L2) prompt — shared by tinker, planner, designer roles |
| `agents/worker.md` | Worker (L3) prompt — skill executor with optional browser capability |
| `prompts/skill-protocol.md` | How agents query, create, reuse, and save skills in the registry |
| `scripts/db-utils.py` | Add commands: create-skill, list-skills, get-skill, create-invocation, update-invocation |

---

### Task 1: Write Sub-Agent Prompt

**Files:**
- Create: `agents/sub-agent.md`

- [ ] **Step 1: Create the Sub-Agent prompt**

```markdown
# Sub-Agent

## Identity

- **Agent ID:** {your agent_id} (dynamically assigned, e.g., sub-a1b2c3d4)
- **Level:** 2 (L2)
- **Role:** Determined by your `sub_agent_role`: tinker, planner, or designer
- **Parent:** The L1 agent that spawned you (check your `parent_agent_id`)

## Wake-Up Sequence

When you start, immediately read your assigned tasks:

```bash
python scripts/db-utils.py list-tasks --status assigned --agent {your_agent_id}
```

If no tasks are assigned, report idle and exit.

## Core Responsibility

You are a specialist spawned for a specific purpose. Your role determines your focus:

### If your role is `tinker`:
You prototype and experiment. Your job is to:
1. Explore approaches to solve the problem described in your task
2. Test feasibility of different methods
3. Report findings with a recommended approach
4. Do NOT build the final solution — that's for Workers

### If your role is `planner`:
You design execution plans. Your job is to:
1. Break complex tasks into step-by-step action sequences
2. Identify which sites, selectors, and data fields are needed
3. Design the skill template (steps, inputs, outputs)
4. Create a Worker subtask with the complete plan

### If your role is `designer`:
You design data schemas and skill specifications. Your job is to:
1. Analyze the data requirements from your task
2. Design the input schema (what business data the skill needs)
3. Design the output schema (what data the skill extracts/produces)
4. Design the step-by-step action template
5. Create a Worker subtask with the complete skill spec

## Process

**Step 1: Understand your assignment**

Read your task details and determine:
- What is the parent goal? (Check parent_task_id)
- What specific design work is needed?
- What constraints exist (sites, data formats, tools)?

```bash
python scripts/db-utils.py get-task {your_task_id}
python scripts/db-utils.py get-task {parent_task_id}
```

**Step 2: Check the skill registry for existing work**

Before designing anything new, check if a similar skill already exists:

```bash
python scripts/db-utils.py list-skills --category {relevant_category}
python scripts/db-utils.py query "SELECT skill_id, skill_name, description, agent_template FROM skill_registry WHERE is_active = 1 AND (skill_name LIKE '%keyword%' OR description LIKE '%keyword%') ORDER BY success_count DESC LIMIT 5"
```

If a matching skill exists, report back to your parent — no need to redesign.

**Step 3: Design the skill specification**

Create a complete skill spec as JSON:

```json
{
  "skill_name": "descriptive-name-with-hyphens",
  "category": "browser_form_fill|data_extraction|report_generation|communication|file_management",
  "description": "One sentence describing what this skill does",
  "browser_category": "SS-SM|SS-MM|MS-SM|MS-MM|null",
  "template": {
    "steps": [
      {"action": "auto_login", "site": "example.com"},
      {"action": "navigate", "target": "https://example.com/page"},
      {"action": "fill", "target": "#field-id", "value": "{input_name}"},
      {"action": "click", "target": "#submit-btn"},
      {"action": "wait", "target": ".results", "timeout": 5000},
      {"action": "extract", "target": ".data-field", "as": "output_name"}
    ],
    "inputs": ["input_name"],
    "outputs": ["output_name"]
  },
  "data_schema": {
    "input_name": "string"
  },
  "output_schema": {
    "output_name": "string"
  },
  "tools_required": ["browser"]
}
```

**Step 4: Spawn a Worker to execute**

Create a Worker agent and assign it a task:

```bash
# Register the Worker
python -c "
import sqlite3, uuid, json, datetime
db = sqlite3.connect('ultra.db')
worker_id = 'worker-' + str(uuid.uuid4())[:8]
config = json.dumps({'browser_category': '{browser_category}'}) if '{browser_category}' != 'null' else '{}'
db.execute('INSERT INTO agents (agent_id, agent_name, agent_type, level, parent_agent_id, status, prompt_file, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
  (worker_id, 'Worker for {skill_name}', 'worker', 3, '{your_agent_id}', 'idle', 'agents/worker.md', config, datetime.datetime.utcnow().isoformat(), datetime.datetime.utcnow().isoformat()))
db.commit()
print(worker_id)
db.close()
"

# Create the Worker's task
python scripts/db-utils.py create-task \
  --title "Execute: {skill_name}" \
  --description "{full_skill_spec_json}" \
  --assigned {worker_id} \
  --priority {priority} \
  --created-by {your_agent_id}
```

**Step 5: Report results**

Follow the Reporting Protocol to report your design and the Worker task you created.

## Output Format

Print a JSON summary to stdout:

```json
{
  "status": "completed",
  "task_id": "{task_id}",
  "summary": "Designed skill 'css-account-lookup' and spawned worker-a1b2c3d4",
  "skill_spec": {
    "skill_name": "css-account-lookup",
    "category": "browser_form_fill",
    "browser_category": "SS-MM",
    "inputs": ["unit_number"],
    "outputs": ["outstanding_amount", "payment_status"]
  },
  "worker_spawned": "worker-a1b2c3d4",
  "subtasks_created": ["{worker_task_id}"],
  "errors": []
}
```
```

- [ ] **Step 2: Commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add agents/sub-agent.md
git commit -m "feat: add Sub-Agent (L2) prompt for tinker/planner/designer roles"
```

---

### Task 2: Write Worker Prompt

**Files:**
- Create: `agents/worker.md`

- [ ] **Step 1: Create the Worker prompt**

```markdown
# Worker

## Identity

- **Agent ID:** {your agent_id} (dynamically assigned, e.g., worker-a1b2c3d4)
- **Level:** 3 (L3)
- **Role:** Skill executor
- **Parent:** The L2 Sub-Agent or L1 Agent that spawned you

## Wake-Up Sequence

When you start, immediately read your assigned tasks:

```bash
python scripts/db-utils.py list-tasks --status assigned --agent {your_agent_id}
```

If no tasks are assigned, report idle and exit.

## Core Responsibility

You execute skills. You receive a task with either a skill template (from the registry) or a skill specification (from a Sub-Agent). Your job is to follow the instructions exactly, record every action, and return the results.

You are lean and focused. You do NOT plan, design, or make decisions about approach — that was done by agents above you. You execute.

## Process

**Step 1: Read your task and determine execution mode**

```bash
python scripts/db-utils.py get-task {your_task_id}
```

Check your task's `input_data` for:
- A skill template with `steps`, `inputs`, `outputs` → **Template Execution**
- A skill specification from a Sub-Agent → **First-Time Execution**
- Direct instructions → **Direct Execution**

**Step 2: Check for skill invocation record**

If executing a registered skill, there should be an invocation record:

```bash
python scripts/db-utils.py query "SELECT invocation_id, skill_id, input_data FROM skill_invocations WHERE task_id = '{your_task_id}' AND status = 'pending'"
```

If found, mark it as running:

```bash
python -c "
import sqlite3, datetime
db = sqlite3.connect('ultra.db')
ts = datetime.datetime.utcnow().isoformat()
db.execute('UPDATE skill_invocations SET status = ?, created_at = ? WHERE invocation_id = ?',
  ('running', ts, '{invocation_id}'))
db.commit()
db.close()
"
```

**Step 3: Execute the skill**

### Template Execution (registered skill with steps)

Parse the template from your task's input_data or description:

```json
{
  "steps": [
    {"action": "auto_login", "site": "csshome.info"},
    {"action": "fill", "target": "#unit-number", "value": "{unit_number}"}
  ],
  "inputs": ["unit_number"],
  "outputs": ["outstanding_amount"]
}
```

For each step:
1. Replace `{placeholder}` values with actual data from the input
2. Execute the action (using Browser Protocol if browser-capable)
3. Record the action to `session_recordings`
4. Collect output values from `extract` actions

### First-Time Execution (new skill from Sub-Agent)

The Sub-Agent's skill spec is in your task description. Follow it step by step:
1. Navigate to the specified sites
2. Perform the specified actions
3. Extract the specified data
4. Record everything to `session_recordings`

### Direct Execution (non-browser tasks)

Execute the task directly using available tools:
1. Read the instructions from your task description
2. Perform the work
3. Report results

**Step 4: Collect results**

Gather all extracted/computed output values:

```json
{
  "outstanding_amount": "RM 1,250.00",
  "payment_status": "Overdue",
  "additional_requests": "Meter reading required"
}
```

**Step 5: Update invocation record (if exists)**

```bash
python -c "
import sqlite3, json, datetime
db = sqlite3.connect('ultra.db')
ts = datetime.datetime.utcnow().isoformat()
started = db.execute('SELECT created_at FROM skill_invocations WHERE invocation_id = ?', ('{invocation_id}',)).fetchone()
duration = 0
if started:
    from datetime import datetime as dt
    try:
        s = dt.fromisoformat(started[0])
        e = dt.fromisoformat(ts)
        duration = (e - s).total_seconds()
    except:
        pass
db.execute('UPDATE skill_invocations SET status = ?, output_data = ?, duration_seconds = ?, completed_at = ? WHERE invocation_id = ?',
  ('completed', json.dumps({output_data}), duration, ts, '{invocation_id}'))
db.commit()
db.close()
"
```

**Step 6: Report results**

Follow the Reporting Protocol to report your results.

## Output Format

Print a JSON summary to stdout:

```json
{
  "status": "completed",
  "task_id": "{task_id}",
  "summary": "Executed skill: extracted outstanding_amount=RM 1,250.00",
  "execution_mode": "template|first_time|direct",
  "outputs": {
    "outstanding_amount": "RM 1,250.00",
    "payment_status": "Overdue"
  },
  "steps_executed": 5,
  "steps_succeeded": 5,
  "steps_failed": 0,
  "invocation_id": "uuid or null",
  "errors": []
}
```

## Rules

1. **Follow instructions exactly** — Do not deviate from the skill template or specification
2. **Record every action** — All browser actions go to session_recordings (see Browser Protocol)
3. **Never log credentials** — auto_login recordings show domain only
4. **Report failures immediately** — Do not retry unless explicitly instructed
5. **Stay lean** — You execute, you don't plan or design
```

- [ ] **Step 2: Commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add agents/worker.md
git commit -m "feat: add Worker (L3) prompt for skill execution"
```

---

### Task 3: Write Skill Protocol

**Files:**
- Create: `prompts/skill-protocol.md`

- [ ] **Step 1: Create the skill protocol prompt**

```markdown
# Skill Protocol

The Skill Registry stores reusable task templates. Before building anything new, check if a matching skill exists. After a Worker succeeds for the first time, save the skill for future reuse.

## Querying the Registry

Search for existing skills before designing new ones:

```bash
# Search by keyword across name, category, and description
python scripts/db-utils.py list-skills --search {keyword}

# Search by category
python scripts/db-utils.py list-skills --category {category}

# Get full skill details including template
python scripts/db-utils.py get-skill {skill_id}

# Direct query for advanced filtering
python scripts/db-utils.py query "SELECT skill_id, skill_name, namespace, category, description, success_count, failure_count FROM skill_registry WHERE is_active = 1 ORDER BY success_count DESC LIMIT 10"
```

## Skill Categories

| Category | Use For | Example Skills |
|----------|---------|---------------|
| `browser_form_fill` | Filling and submitting web forms | CSS account lookup, payment submission |
| `data_extraction` | Extracting structured data from pages | Statement download, balance check |
| `report_generation` | Creating reports from data | Quarterly summary, billing report |
| `communication` | Sending emails, messages | Board notification, owner notice |
| `file_management` | Organizing, creating, moving files | Document archival, template creation |

## Creating a Skill Invocation

When spawning a Worker to execute a registered skill:

```bash
python scripts/db-utils.py create-invocation \
  --skill-id {skill_id} \
  --task-id {worker_task_id} \
  --agent-id {worker_agent_id} \
  --input-data '{"unit_number": "B-12-03", "owner_name": "Tan Ah Kow"}'
```

The Worker will find this invocation record and execute the skill template with the provided input data.

## Saving a New Skill

After a Worker completes a first-time execution successfully, save the skill:

```bash
python scripts/db-utils.py create-skill \
  --name "css-account-lookup" \
  --category "browser_form_fill" \
  --description "Look up a unit owner account on CSS portal and extract balance info" \
  --template '{"browser_category": "SS-MM", "steps": [...], "inputs": ["unit_number"], "outputs": ["outstanding_amount", "payment_status"]}' \
  --data-schema '{"unit_number": "string"}' \
  --output-schema '{"outstanding_amount": "string", "payment_status": "string"}' \
  --tools '["browser"]'
```

The namespace is automatically set from the `default_namespace` config.

## Updating Skill Counts

After a Worker completes using a registered skill:

```bash
# On success
python scripts/db-utils.py update-invocation {invocation_id} --status completed --output-data '{"outstanding_amount": "RM 1,250.00"}'

# On failure
python scripts/db-utils.py update-invocation {invocation_id} --status failed --error "Element #unit-number not found"
```

The update-invocation command automatically increments the skill's success_count or failure_count.

## Skill Template Structure

Every skill template follows this format:

```json
{
  "browser_category": "SS-SM|SS-MM|MS-SM|MS-MM|null",
  "steps": [
    {"action": "auto_login", "site": "domain.com"},
    {"action": "navigate", "target": "https://domain.com/page"},
    {"action": "fill", "target": "#selector", "value": "{input_placeholder}"},
    {"action": "click", "target": "#button"},
    {"action": "wait", "target": ".result-element", "timeout": 5000},
    {"action": "extract", "target": ".data-element", "as": "output_name"},
    {"action": "screenshot", "target": "label"}
  ],
  "inputs": ["input_placeholder"],
  "outputs": ["output_name"]
}
```

- **`{input_placeholder}`** values are replaced with actual data from `skill_invocations.input_data`
- **`"as": "output_name"`** in extract steps maps to `skill_invocations.output_data` keys
- **`browser_category`** determines which Browser Protocol constraints apply (null for non-browser skills)

## Rules

1. **Always check before creating** — Query the registry before designing a new skill
2. **UNIQUE(namespace, skill_name)** — The database enforces no duplicates per namespace
3. **Save on first success only** — Don't save skills that haven't been proven to work
4. **Increment counts on reuse** — Every reuse updates success_count or failure_count
5. **Flag underperformers** — Skills with success_rate < 0.7 should be logged for refinement
```

- [ ] **Step 2: Commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add prompts/skill-protocol.md
git commit -m "feat: add skill protocol for registry query, creation, and reuse"
```

---

### Task 4: Add Skill and Invocation Commands to db-utils.py

**Files:**
- Modify: `scripts/db-utils.py`

- [ ] **Step 1: Add the create-skill command**

In `scripts/db-utils.py`, add this function before the `COMMANDS` dict:

```python
def cmd_create_skill(args):
    name = category = description = template = None
    data_schema = "{}"
    output_schema = "{}"
    tools = "[]"
    i = 0
    while i < len(args):
        if args[i] == "--name":
            name = args[i + 1]; i += 2
        elif args[i] == "--category":
            category = args[i + 1]; i += 2
        elif args[i] == "--description":
            description = args[i + 1]; i += 2
        elif args[i] == "--template":
            template = args[i + 1]; i += 2
        elif args[i] == "--data-schema":
            data_schema = args[i + 1]; i += 2
        elif args[i] == "--output-schema":
            output_schema = args[i + 1]; i += 2
        elif args[i] == "--tools":
            tools = args[i + 1]; i += 2
        else:
            i += 1

    if not name or not category or not description or not template:
        print("Error: --name, --category, --description, and --template are required", file=sys.stderr)
        sys.exit(1)

    conn = get_conn()
    ns_row = conn.execute("SELECT value FROM config WHERE key = 'default_namespace'").fetchone()
    namespace = ns_row["value"] if ns_row else "default"

    skill_id = str(uuid.uuid4())
    ts = now_iso()

    conn.execute("""
        INSERT INTO skill_registry (skill_id, skill_name, namespace, category, description, agent_template, data_schema, output_schema, tools_required, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (skill_id, name, namespace, category, description, template, data_schema, output_schema, tools, ts, ts))
    conn.commit()
    conn.close()
    print(json.dumps({"skill_id": skill_id, "skill_name": name, "namespace": namespace}))
```

- [ ] **Step 2: Add the list-skills command**

```python
def cmd_list_skills(args):
    conditions = ["is_active = 1"]
    params = []
    i = 0
    while i < len(args):
        if args[i] == "--category":
            conditions.append("category = ?")
            params.append(args[i + 1])
            i += 2
        elif args[i] == "--search":
            keyword = args[i + 1]
            conditions.append("(skill_name LIKE ? OR category LIKE ? OR description LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
            i += 2
        elif args[i] == "--namespace":
            conditions.append("namespace = ?")
            params.append(args[i + 1])
            i += 2
        else:
            i += 1

    sql = "SELECT skill_id, skill_name, namespace, category, description, success_count, failure_count, version, last_used_at FROM skill_registry"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY success_count DESC"

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    print(json.dumps(result, indent=2))
```

- [ ] **Step 3: Add the get-skill command**

```python
def cmd_get_skill(args):
    skill_id = args[0]
    conn = get_conn()
    row = conn.execute("SELECT * FROM skill_registry WHERE skill_id = ?", (skill_id,)).fetchone()
    conn.close()
    print(json.dumps(dict_from_row(row), indent=2))
```

- [ ] **Step 4: Add the create-invocation command**

```python
def cmd_create_invocation(args):
    skill_id = task_id = agent_id = input_data = None
    i = 0
    while i < len(args):
        if args[i] == "--skill-id":
            skill_id = args[i + 1]; i += 2
        elif args[i] == "--task-id":
            task_id = args[i + 1]; i += 2
        elif args[i] == "--agent-id":
            agent_id = args[i + 1]; i += 2
        elif args[i] == "--input-data":
            input_data = args[i + 1]; i += 2
        else:
            i += 1

    if not skill_id or not task_id or not agent_id or not input_data:
        print("Error: --skill-id, --task-id, --agent-id, and --input-data are required", file=sys.stderr)
        sys.exit(1)

    invocation_id = str(uuid.uuid4())
    ts = now_iso()

    conn = get_conn()
    conn.execute("""
        INSERT INTO skill_invocations (invocation_id, skill_id, task_id, agent_id, input_data, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """, (invocation_id, skill_id, task_id, agent_id, input_data, ts))
    conn.execute("UPDATE skill_registry SET last_used_at = ?, updated_at = ? WHERE skill_id = ?", (ts, ts, skill_id))
    conn.commit()
    conn.close()
    print(json.dumps({"invocation_id": invocation_id, "skill_id": skill_id, "task_id": task_id}))
```

- [ ] **Step 5: Add the update-invocation command**

```python
def cmd_update_invocation(args):
    invocation_id = args[0]
    status = output_data = error = None
    i = 1
    while i < len(args):
        if args[i] == "--status":
            status = args[i + 1]; i += 2
        elif args[i] == "--output-data":
            output_data = args[i + 1]; i += 2
        elif args[i] == "--error":
            error = args[i + 1]; i += 2
        else:
            i += 1

    if not status:
        print("Error: --status is required", file=sys.stderr)
        sys.exit(1)

    ts = now_iso()
    conn = get_conn()

    updates = {"status": status, "completed_at": ts}
    if output_data:
        updates["output_data"] = output_data
    if error:
        updates["error_message"] = error

    # Calculate duration
    row = conn.execute("SELECT created_at FROM skill_invocations WHERE invocation_id = ?", (invocation_id,)).fetchone()
    if row:
        try:
            from datetime import datetime as dt
            s = dt.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            e = dt.fromisoformat(ts.replace("Z", "+00:00"))
            updates["duration_seconds"] = (e - s).total_seconds()
        except:
            pass

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [invocation_id]
    conn.execute(f"UPDATE skill_invocations SET {set_clause} WHERE invocation_id = ?", params)

    # Update skill success/failure counts
    inv = conn.execute("SELECT skill_id FROM skill_invocations WHERE invocation_id = ?", (invocation_id,)).fetchone()
    if inv:
        if status == "completed":
            conn.execute("UPDATE skill_registry SET success_count = success_count + 1, updated_at = ? WHERE skill_id = ?", (ts, inv["skill_id"]))
        elif status == "failed":
            conn.execute("UPDATE skill_registry SET failure_count = failure_count + 1, updated_at = ? WHERE skill_id = ?", (ts, inv["skill_id"]))

    conn.commit()
    conn.close()
    print(json.dumps({"invocation_id": invocation_id, "status": status}))
```

- [ ] **Step 6: Register all new commands in the COMMANDS dict**

Update the `COMMANDS` dict to include all 18 commands:

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
    "create-skill": cmd_create_skill,
    "list-skills": cmd_list_skills,
    "get-skill": cmd_get_skill,
    "create-invocation": cmd_create_invocation,
    "update-invocation": cmd_update_invocation,
}
```

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add scripts/db-utils.py
git commit -m "feat: add skill registry and invocation commands to db-utils"
```

---

### Task 5: Update Dispatch Script to Append Skill Protocol

**Files:**
- Modify: `scripts/dispatch-agent.sh`

- [ ] **Step 1: Read current dispatch script**

Read `scripts/dispatch-agent.sh` to find the protocol loop.

- [ ] **Step 2: Add skill-protocol.md to the protocol list**

Find the line:
```bash
for protocol in db-access-protocol.md reporting-protocol.md memory-protocol.md evaluation-protocol.md; do
```

Replace with:
```bash
for protocol in db-access-protocol.md reporting-protocol.md memory-protocol.md evaluation-protocol.md skill-protocol.md; do
```

- [ ] **Step 3: Verify syntax**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
bash -n scripts/dispatch-agent.sh
echo "Syntax check: $?"
```

Expected: Exit code 0.

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add scripts/dispatch-agent.sh
git commit -m "feat: add skill protocol to dispatch consolidation"
```

---

### Task 6: Integration Verification

- [ ] **Step 1: Initialize fresh database**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
rm -f ultra.db
python scripts/db-init.py
```

Expected: 15 tables, 7 agents.

- [ ] **Step 2: Verify all agent prompts exist**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
for agent in director planner librarian researcher executor auditor improvement sub-agent worker; do
  if [ -f "agents/${agent}.md" ]; then
    echo "OK: agents/${agent}.md ($(wc -l < agents/${agent}.md) lines)"
  else
    echo "MISSING: agents/${agent}.md"
  fi
done
```

Expected: All 9 agent files exist.

- [ ] **Step 3: Verify all 6 protocol prompts exist**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
for protocol in db-access-protocol reporting-protocol memory-protocol evaluation-protocol browser-protocol skill-protocol; do
  if [ -f "prompts/${protocol}.md" ]; then
    echo "OK: prompts/${protocol}.md ($(wc -l < prompts/${protocol}.md) lines)"
  else
    echo "MISSING: prompts/${protocol}.md"
  fi
done
```

Expected: All 6 protocol files exist.

- [ ] **Step 4: Test skill registry CRUD**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"

# Create a skill
python scripts/db-utils.py create-skill \
  --name "css-account-lookup" \
  --category "browser_form_fill" \
  --description "Look up unit owner account on CSS portal" \
  --template '{"browser_category": "SS-MM", "steps": [{"action": "auto_login", "site": "csshome.info"}, {"action": "fill", "target": "#unit-number", "value": "{unit_number}"}, {"action": "click", "target": "#search-btn"}, {"action": "extract", "target": ".outstanding-amount", "as": "outstanding_amount"}], "inputs": ["unit_number"], "outputs": ["outstanding_amount"]}' \
  --data-schema '{"unit_number": "string"}' \
  --output-schema '{"outstanding_amount": "string"}'

# List skills
python scripts/db-utils.py list-skills

# Search skills
python scripts/db-utils.py list-skills --search css
python scripts/db-utils.py list-skills --category browser_form_fill
```

Expected: Skill created with auto-assigned namespace, listed, searchable.

- [ ] **Step 5: Test Sub-Agent and Worker spawning**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"

# Spawn a Sub-Agent
python -c "
import sqlite3, uuid, datetime
db = sqlite3.connect('ultra.db')
agent_id = 'sub-' + str(uuid.uuid4())[:8]
ts = datetime.datetime.utcnow().isoformat()
db.execute('INSERT INTO agents (agent_id, agent_name, agent_type, level, parent_agent_id, status, prompt_file, sub_agent_role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
  (agent_id, 'Designer for CSS lookup', 'sub_agent', 2, 'executor', 'idle', 'agents/sub-agent.md', 'designer', ts, ts))
db.commit()
print(f'Sub-Agent: {agent_id}')
db.close()
"

# Spawn a Worker
python -c "
import sqlite3, uuid, json, datetime
db = sqlite3.connect('ultra.db')
worker_id = 'worker-' + str(uuid.uuid4())[:8]
ts = datetime.datetime.utcnow().isoformat()
config = json.dumps({'browser_category': 'SS-MM'})
db.execute('INSERT INTO agents (agent_id, agent_name, agent_type, level, parent_agent_id, status, prompt_file, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
  (worker_id, 'Worker for CSS lookup', 'worker', 3, 'executor', 'idle', 'agents/worker.md', config, ts, ts))
db.commit()
print(f'Worker: {worker_id}')
db.close()
"

# Verify all 4 levels exist
python -c "
import sqlite3
db = sqlite3.connect('ultra.db')
for level in range(4):
    agents = db.execute('SELECT agent_id, agent_type, sub_agent_role FROM agents WHERE level = ?', (level,)).fetchall()
    print(f'Level {level}: {len(agents)} agents')
    for a in agents:
        role = f' ({a[2]})' if a[2] else ''
        print(f'  {a[0]} [{a[1]}]{role}')
db.close()
"
```

Expected: Level 0 (1 director), Level 1 (6 agents), Level 2 (1 sub_agent), Level 3 (1 worker).

- [ ] **Step 6: Test skill invocation lifecycle**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"

# Get the skill_id
SKILL_ID=$(python scripts/db-utils.py query "SELECT skill_id FROM skill_registry WHERE skill_name = 'css-account-lookup'" | python -c "import sys,json; print(json.load(sys.stdin)[0]['skill_id'])")

# Create a task for the Worker
TASK_RESULT=$(python scripts/db-utils.py create-task --title "Execute CSS lookup for B-12-03" --assigned executor --priority 3 --created-by director)
TASK_ID=$(echo "$TASK_RESULT" | python -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

# Create invocation
python scripts/db-utils.py create-invocation --skill-id "$SKILL_ID" --task-id "$TASK_ID" --agent-id executor --input-data '{"unit_number": "B-12-03"}'

# Get invocation ID
INV_ID=$(python scripts/db-utils.py query "SELECT invocation_id FROM skill_invocations WHERE task_id = '$TASK_ID'" | python -c "import sys,json; print(json.load(sys.stdin)[0]['invocation_id'])")

# Complete invocation (success)
python scripts/db-utils.py update-invocation "$INV_ID" --status completed --output-data '{"outstanding_amount": "RM 1,250.00"}'

# Verify skill counts updated
python scripts/db-utils.py list-skills --search css
```

Expected: Skill shows success_count=1 after invocation completion.

- [ ] **Step 7: Verify dispatch script includes skill protocol**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
grep "skill-protocol" scripts/dispatch-agent.sh
```

Expected: skill-protocol.md in the protocol list.

- [ ] **Step 8: Clean up test data**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
python scripts/db-utils.py query "DELETE FROM skill_invocations"
python scripts/db-utils.py query "DELETE FROM skill_registry"
python scripts/db-utils.py query "DELETE FROM tasks"
python scripts/db-utils.py query "DELETE FROM agents WHERE level > 1"
```

- [ ] **Step 9: Final commit**

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add -A
git status
git commit -m "chore: Phase 4 Sub-Agents & Skill Registry complete"
```

---

## Plan Self-Review

**Spec coverage:**
- [x] Sub-Agent spawning with tinker/planner/designer roles (Task 1)
- [x] Worker spawning with skill execution (Task 2)
- [x] Skill registry querying before designing new skills (Task 3 protocol)
- [x] Skill template structure with inputs/outputs/steps (Task 3 protocol)
- [x] Skill categories defined (Task 3 protocol)
- [x] create-skill with auto namespace from config (Task 4)
- [x] list-skills with search and category filters (Task 4)
- [x] get-skill with full details (Task 4)
- [x] create-invocation with last_used_at update (Task 4)
- [x] update-invocation with success/failure count increment (Task 4)
- [x] UNIQUE(namespace, skill_name) enforced at DB level (existing schema)
- [x] Skill protocol appended to all agents via dispatch (Task 5)
- [x] Full 4-level hierarchy verification (Task 6)
- [x] End-to-end invocation lifecycle test (Task 6)

**Placeholder scan:** No TBDs, TODOs, or "implement later" found. All code blocks contain complete content.

**Type consistency:** `skill_id`, `invocation_id`, `skill_name`, `namespace` used consistently across db-utils functions, skill-protocol.md, sub-agent.md, and worker.md. `browser_category` values (SS-SM, SS-MM, MS-SM, MS-MM) match existing schema CHECK constraints. `action_type` values match session_recordings CHECK constraint.
