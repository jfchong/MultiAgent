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
