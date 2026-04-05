# Ultra Agent System

Multi-agent orchestration platform running inside Claude Code CLI.

## Project Structure

- `agents/` — Agent system prompts (one per agent)
- `frameworks/` — Top 20 approach framework prompts
- `toolkits/` — 36 mini-toolkit prompts
- `skills/` — Saved Worker skill templates (auto-populated)
- `scripts/` — Python/Bash operational scripts
- `prompts/` — Shared prompt fragments included in all agents
- `ui/` — Work Release Web UI
- `ultra.db` — SQLite database (all state)

## Key Commands

```bash
# Initialize/reset database
python scripts/db-init.py

# Query database
python scripts/db-utils.py query "SELECT * FROM agents"
python scripts/db-utils.py list-tasks --status pending
python scripts/db-utils.py get-config default_namespace

# Dispatch an agent
bash scripts/dispatch-agent.sh <agent_id> <task_id> [model] [--background]
```

## Architecture

- **Director** (L0): Claude Code Skill, entry point
- **Agents** (L1): 6 specialists dispatched as `claude -p` sessions
- **Sub-Agents** (L2): Tinkers/Planners/Designers, spawned by L1
- **Workers** (L3): Skill executors, spawned by L2
- **SQLite**: Single source of truth (WAL mode for concurrency)
- **Cron Manager**: 1-min tick, parallel dispatch
- **Work Release**: Human approval gate with learnable auto-release

## Default Namespace

`jfchong.alliedgroup` — configurable via `python scripts/db-utils.py set-config default_namespace <value>`
