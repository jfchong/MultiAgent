# Ultra Agent System

Multi-agent orchestration platform running inside Claude Code CLI.

## Project Structure

| Path | Description |
|------|-------------|
| `agents/` | Agent system prompts — one file per agent type (9 total) |
| `frameworks/` | Top 20 approach framework prompts for task methodology |
| `toolkits/` | 36 mini-toolkit prompts for specialized capabilities |
| `skills/` | Saved Worker skill templates (auto-populated by Librarian) |
| `scripts/` | Python/Bash operational scripts |
| `prompts/` | Shared protocol fragments included in all agents |
| `ui/` | Work Release Web UI (served by release-server.py) |
| `ultra.db` | SQLite database — single source of truth (WAL mode) |
| `docs/` | Plans, architecture notes, and phase documentation |

## Architecture

4-level hierarchy where every level communicates exclusively through SQLite:

| Level | Role | Count | Spawned By | Notes |
|-------|------|--------|------------|-------|
| L0 | Director | 1 | Human (Claude Code skill) | Entry point, task router |
| L1 | Agents | 6 | Director | `claude -p` sessions |
| L2 | Sub-Agents | N | L1 Agents | Tinkers / Planners / Designers |
| L3 | Workers | N | L2 Sub-Agents | Skill executors |

### Agent Types (9 files in `agents/`)

| File | Role | Level |
|------|------|-------|
| `director.md` | Routes tasks, manages cron, oversees all L1 agents | L0 |
| `executor.md` | Executes browser/API tasks end-to-end | L1 |
| `planner.md` | Decomposes complex tasks into sub-tasks | L1 |
| `researcher.md` | Information gathering, web research | L1 |
| `librarian.md` | Manages skill registry, indexing, retrieval | L1 |
| `improvement.md` | Evaluates agent performance, suggests improvements | L1 |
| `auditor.md` | Security, compliance, quality auditing | L1 |
| `sub-agent.md` | Generic sub-agent spawned by L1 agents | L2 |
| `worker.md` | Executes a specific named skill from the registry | L3 |

## Protocols (in `prompts/`)

All agents include these 6 protocol fragments:

| File | Purpose |
|------|---------|
| `memory-protocol.md` | Short-term (session) and long-term (SQLite) memory rules |
| `evaluation-protocol.md` | Mandatory self-evaluation after every task |
| `reporting-protocol.md` | Structured output format for task completion |
| `skill-protocol.md` | How to look up, invoke, and register skills |
| `db-access-protocol.md` | Safe SQLite read/write patterns via db-utils.py |
| `browser-protocol.md` | Browser automation safety and session recording |

## Scripts

| Script | Description |
|--------|-------------|
| `scripts/db-init.py` | Initialize or reset the database schema (destructive) |
| `scripts/db-utils.py` | CLI for all database operations (24 commands) |
| `scripts/dispatch-agent.sh` | Launch an L1 agent as a `claude -p` session |
| `scripts/cron-manager.py` | 1-minute tick loop — polls tasks and dispatches agents |
| `scripts/health-check.py` | Check agent/session health, detect stuck agents |
| `scripts/release-server.py` | HTTP server for the Work Release approval UI |
| `scripts/e2e-verify.py` | End-to-end system integration tests |

### Script Usage

```bash
# Initialize/reset database (DESTRUCTIVE — clears all data)
python scripts/db-init.py

# Dispatch an agent
bash scripts/dispatch-agent.sh <agent_id> <task_id> [model] [--background]

# Start cron manager (blocks, runs every 60s)
python scripts/cron-manager.py

# Check system health
python scripts/health-check.py

# Start Work Release UI server (default port 8080)
python scripts/release-server.py

# Run end-to-end verification
python scripts/e2e-verify.py
```

## Key Commands — db-utils.py (24 commands)

```bash
python scripts/db-utils.py <command> [args]
```

### Core

| Command | Usage |
|---------|-------|
| `query` | `query "SELECT * FROM agents"` — raw SQL select |

### Agents

| Command | Usage |
|---------|-------|
| `get-agent` | `get-agent <agent_id>` |
| `list-agents` | `list-agents [--status idle] [--level 1] [--type executor] [--parent <id>]` |
| `create-agent` | `create-agent --name "Tinker-ABC" --type sub_agent --level 2 [--parent <id>] [--prompt-file agents/sub-agent.md] [--sub-role tinker]` |
| `update-agent` | `update-agent <agent_id> --status idle [--config '{"key":"val"}']` |

### Tasks

| Command | Usage |
|---------|-------|
| `get-task` | `get-task <task_id>` |
| `list-tasks` | `list-tasks [--status pending] [--agent planner]` |
| `create-task` | `create-task --title "..." --description "..." [--assigned planner] [--priority 3]` |
| `update-task` | `update-task <task_id> --status in_progress` |

### Config

| Command | Usage |
|---------|-------|
| `get-config` | `get-config <key>` |
| `set-config` | `set-config <key> <value>` |

### Sessions

| Command | Usage |
|---------|-------|
| `list-sessions` | `list-sessions [--status running] [--agent executor] [--task <id>] [--limit 50]` |
| `get-session` | `get-session <session_id>` — includes step recordings |

### Credentials

| Command | Usage |
|---------|-------|
| `create-credential` | `create-credential --domain example.com --label "Main" [--auth-type password] [--username u] [--password p] [--api-key k]` |
| `list-credentials` | `list-credentials` |
| `delete-credential` | `delete-credential <site_domain>` |

### Skills

| Command | Usage |
|---------|-------|
| `create-skill` | `create-skill --name "..." --category "..." --description "..." --template "..." [--tools '["bash"]']` |
| `list-skills` | `list-skills [--category web] [--search keyword] [--namespace jfchong.alliedgroup]` |
| `get-skill` | `get-skill <skill_id>` |

### Invocations

| Command | Usage |
|---------|-------|
| `create-invocation` | `create-invocation --skill-id <id> --task-id <id> --agent-id <id> --input-data '{...}'` |
| `update-invocation` | `update-invocation <invocation_id> --status completed [--output-data '{...}'] [--error "msg"]` |

### Releases

| Command | Usage |
|---------|-------|
| `create-release` | `create-release --task-id <id> --agent-id <id> --title "..." --action-type execute [--description "..."] [--agent-level 1]` |
| `list-releases` | `list-releases [--status pending] [--agent executor] [--level 1] [--action-type execute]` |
| `update-release` | `update-release <release_id> --status approved` (or `rejected`) |

## Work Release Flow

Agents pause before irreversible actions and create a work release:

```
Agent creates release → status: "pending"
        ↓
Cron detects pending release → notifies UI
        ↓
Human reviews in Web UI (release-server.py)
        ↓
  Approved → task resumes (status: in_progress)
  Rejected → task fails  (status: failed)
        ↓
Auto-release rules: if a matching rule exists,
  release is immediately set to "auto_released"
  and task continues without human intervention
```

**Auto-release rules** are stored in `auto_release_rules` table and match on `agent_type`, `action_type`, and optional `title_pattern`. Useful for low-risk repeated actions.

## Cron Manager

`scripts/cron-manager.py` runs a 1-minute tick cycle:

1. **Health check** — detect stuck agents (timeout from config), mark failed
2. **Pending tasks** — query tasks with status `pending` or `assigned`
3. **Parallel dispatch** — call `dispatch-agent.sh` for each eligible task (up to `max_concurrent_agents`)
4. **Release check** — scan for `pending` work releases, trigger UI notification
5. **Sleep 60s** — repeat

## Configuration

Key config values (stored in `config` table, read via `get-config`):

| Key | Default | Description |
|-----|---------|-------------|
| `default_namespace` | `jfchong.alliedgroup` | Skill registry namespace |
| `max_concurrent_agents` | `5` | Max parallel L1 agent sessions |
| `stuck_agent_timeout_minutes` | `30` | Minutes before agent is marked stuck |
| `release_server_port` | `8080` | Work Release UI port |
| `auto_release_enabled` | `true` | Global toggle for auto-release rules |

```bash
# Read a config value
python scripts/db-utils.py get-config default_namespace

# Set a config value
python scripts/db-utils.py set-config default_namespace myorg.team
python scripts/db-utils.py set-config max_concurrent_agents 3
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ultra.db` missing or corrupt | Run `python scripts/db-init.py` to recreate schema |
| Agent stuck in `running` | Run `python scripts/health-check.py`; or `update-agent <id> --status idle` |
| Task stuck in `awaiting_release` | Open Work Release UI or run `update-release <id> --status approved` |
| Cron not dispatching | Check `max_concurrent_agents`; verify no tasks in error state blocking queue |
| Skill not found | Run `list-skills --search <keyword>`; check namespace matches `default_namespace` |
| `dispatch-agent.sh` fails | Verify `claude` CLI is on PATH; check agent prompt file exists in `agents/` |
| Sessions accumulating | Sessions are append-only; query `list-sessions --status running --limit 10` to find orphans |
