# Ultra Agent System — Design Specification

**Date:** 2026-04-05
**Status:** Approved
**Author:** JF Chong + Claude

## Overview

A hierarchical multi-agent orchestration platform running inside Claude Code CLI. Uses a 4-level agent hierarchy (Director -> Agents -> Sub-Agents -> Workers) with SQLite as the central coordination layer, a centralized Cron Manager for scheduling with parallel dispatch, and a layered "Ultra Prompt" system (frameworks + toolkits + evaluation). Features a Skill Registry for Worker reuse and a human-in-the-loop Work Release gate with learnable auto-release rules.

## Architecture Decision

**Hybrid: Skill Shell + CLI Dispatch**
- Director is a Claude Code Skill (user-facing entry point)
- All other agents dispatched as independent `claude -p` CLI sessions
- SQLite DB is the single source of truth for all state
- Cron Manager (1-min tick) wakes agents, supports parallel dispatch
- Each agent can run multiple instances in parallel
- Work Release gate: ALL agent outputs park for user approval. Auto-release trains the system over time.

---

## 4-Level Hierarchy

### Level 0: DIRECTOR (Claude Code Skill)
- Intake, normalize, pick frameworks, dispatch, aggregate results
- Owns the Cron Manager
- User-facing entry point

### Level 1: AGENTS (6 specialists, CLI sessions)
| Agent | Responsibility |
|-------|---------------|
| **Planner** | Orchestrate workflows, decompose goals, distribute tasks |
| **Librarian** | Database access, data storage, file organization |
| **Researcher** | Info sufficiency check, web search, structured findings |
| **Executor** | Implementation, spawn Sub-Agents for skill design |
| **Auditor** | Quality review, evaluation toolkits, post-mortems |
| **Improvement** | Activity summaries, pattern recognition, optimization |

All L1 agents can spawn Sub-Agents when they need to decompose complex work.

### Level 2: SUB-AGENTS (Tinkers/Planners/Designers, CLI sessions)
- Figure out HOW to accomplish tasks
- Design skill specs and data schemas for Workers
- Prototype approaches, test feasibility
- Write Worker instructions
- Spawned by ANY Level 1 Agent

### Level 3: WORKERS (Skill executors, CLI sessions)
- DO the actual work using saved skills
- One skill per task type (no duplicates)
- Only data changes between invocations
- First-time skills saved to registry on success
- Spawned by Level 2 Sub-Agents

---

## Project Directory Structure

```
C:\Users\jfcho\Desktop\CoWork\MultiAgent\
├── CLAUDE.md                        # Project-level Claude instructions
├── ultra.db                         # SQLite database (all state)
├── agents/                          # Agent prompt templates
│   ├── director.md
│   ├── planner.md
│   ├── librarian.md
│   ├── researcher.md
│   ├── executor.md
│   ├── auditor.md
│   └── improvement.md
├── frameworks/                      # Top 20 Frameworks Catalog
│   ├── catalog.md
│   └── approach/                    # Individual framework prompts
├── toolkits/                        # 36-Toolkit Library
│   ├── catalog.md
│   ├── planning/
│   ├── research/
│   ├── execution/
│   ├── evaluation/                  # Mandatory (quality-gate, constraint-compliance, etc.)
│   └── improvement/
├── skills/                          # Saved Worker skill templates (runtime populated)
├── scripts/                         # Operational scripts
│   ├── db-init.py
│   ├── db-utils.py
│   ├── cron-manager.py
│   ├── dispatch-agent.sh
│   ├── health-check.py
│   └── release-server.py
├── ui/                              # Work Release Web UI
│   ├── index.html
│   ├── style.css
│   └── app.js
├── prompts/                         # Shared prompt fragments
│   ├── memory-protocol.md
│   ├── evaluation-protocol.md
│   ├── reporting-protocol.md
│   └── db-access-protocol.md
├── logs/
└── docs/
```

---

## SQLite Schema (ultra.db)

### agents
All agent instances across all 4 levels. Fields: agent_id, agent_name, agent_type, level (0-3), parent_agent_id, status (idle/running/error/retired), prompt_file, skill_id (Workers), sub_agent_role (Sub-Agents: tinker/planner/designer), config_json, timestamps, counters, session_id.

### tasks
Central work-tracking. Fields: task_id, parent_task_id, title, description, status (pending/assigned/awaiting_release/in_progress/blocked/review/completed/failed/cancelled), priority (1-10), assigned_agent, created_by, framework, toolkits_json, input_data, output_data, error_message, depends_on_json, timestamps, retry_count, max_retries.

### memory_long
Persistent long-term memory. Fields: memory_id, agent_id (or 'shared'), category (fact/preference/approach/domain_knowledge/relationship/pattern/constraint), subject, content, confidence (0-1), source, tags_json, access_count, timestamps, expires_at.

### memory_short
Task-scoped working memory. Fields: memory_id, task_id, agent_id, key, value. UNIQUE(task_id, agent_id, key). Cleared on task completion.

### skill_registry
Saved Worker skills (no duplicates). Fields: skill_id, skill_name, namespace, category, description, agent_template, data_schema, output_schema, tools_required, success_count, failure_count, version, is_active, timestamps. UNIQUE(namespace, skill_name).

### skill_invocations
Audit trail for skill executions. Fields: invocation_id, skill_id, task_id, agent_id, input_data, output_data, status, duration_seconds, error_message.

### cron_schedule
Cron Manager schedule. Fields: schedule_id, agent_id, cron_expression, task_template, is_enabled, timestamps, fire_count, max_fires.

### events
Chronological audit log. Fields: event_id, event_type, agent_id, task_id, data_json, created_at.

### work_releases
Human-in-the-loop approval gate. Fields: release_id, task_id, agent_id, agent_level, title, description, action_type (plan/research/design/execute/review/store), input_preview, output_preview, status (pending/approved/rejected/auto_released), auto_release, auto_release_rule_id, reviewed_at, created_at.

### auto_release_rules
Learned auto-approval patterns. Fields: rule_id, match_agent_type, match_action_type, match_skill_id, match_title_pattern, is_enabled, created_from_release_id, fire_count, created_at.

### improvement_log
Pattern tracking. Fields: log_id, task_id, agent_id, category (success_pattern/failure_pattern/approach_rating/toolkit_feedback/skill_refinement/process_suggestion), summary, details, impact_score (-1 to 1), action_taken.

---

## Task State Machine

```
pending -> assigned -> awaiting_release -> [APPROVED] -> in_progress -> review -> completed
                           |                                  |            |
                       rejected                            failed    rejected (back to in_progress)
                                                              |
                                                         retry or cancel

Auto-release path: awaiting_release -> [RULE MATCHES] -> in_progress (skips human)
Dependency: pending -> blocked -> assigned (when deps resolve)
```

---

## Work Release System

### Flow
1. Agent completes planning, writes proposed action to `work_releases` (status=pending)
2. Task moves to `awaiting_release`
3. Cron Manager checks `auto_release_rules` -- if match, auto-approve
4. If no rule, item appears in Web UI at localhost:53800
5. User reviews: Approve / Approve+Auto-release / Reject
6. Auto-release creates a rule for future matching
7. Approved task moves to `in_progress`, agent dispatched

### Web UI (localhost:53800)
- Pending releases table grouped by agent level
- Per-item: Approve checkbox, Reject button, Auto-release toggle
- Batch: "Approve All", "Approve All for Agent Type"
- Auto-release rule management
- Live refresh (5s polling)
- Status bar: running agents, pending count, rules active

### API Endpoints
- GET/POST /api/releases -- list, approve, reject, auto-release
- GET/DELETE /api/rules -- manage auto-release rules
- GET /api/status -- system health

---

## Skill Registry

### Reuse Pattern
1. Sub-Agent queries registry before creating new skill
2. Match found -> reuse with new data payload
3. No match -> design new skill spec, spawn Worker
4. Worker succeeds -> save skill permanently
5. Worker fails -> don't save, log failure

### Naming: `{namespace}.{skill_name}`
- Default namespace in config (e.g., `jfchong.alliedgroup`)
- AI can derive more specific namespace from context
- Override per-skill possible

### No Duplicates: UNIQUE(namespace, skill_name) enforced at DB level

---

## Cron Manager

- 1-minute tick loop (`scripts/cron-manager.py`)
- Parallel dispatch via backgrounded `claude -p` processes
- Multi-instance: same agent type can run multiple concurrent instances
- SQLite WAL mode for concurrent access
- Max 5 concurrent instances (configurable, default 2 per type)
- Priority ordering (1=highest), 30s cooldown per instance
- Auto-release rule checking on each tick
- Health check: stuck agents (>10 min) -> error state

---

## Ultra Prompt Layering

```
Layer 0: Base Agent Prompt (agents/{name}.md)
Layer 1: Framework (frameworks/{framework}.md) -- Director picks
Layer 2: Toolkits (toolkits/{cat}/{name}.md) -- Agent picks 1-3
Layer 3: Mandatory Evaluation (toolkits/evaluation/*.md)
Layer 4: Protocols (prompts/*.md)
```

Inheritance: L2 Sub-Agents inherit parent's framework + toolkits. L3 Workers use skill template + inherited context.

---

## Memory System

### Long-term (memory_long)
- Persists in SQLite across sessions
- Cross-agent sharing via agent_id='shared'
- AI determines what to save per `prompts/memory-protocol.md`

### Short-term (memory_short)
- Task-scoped key-value pairs
- Auto-cleared on task completion

---

## Implementation Phases

1. **Foundation** -- Directory structure, db-init.py, CLAUDE.md, director.md, planner.md, dispatch-agent.sh
2. **Core Agents** -- All 6 agent prompts, memory/evaluation protocols, dependency resolution
3. **Frameworks & Toolkits** -- Catalog + top 6 frameworks, 4 evaluation + 8 priority toolkits
4. **Sub-Agents & Skill Registry** -- Sub-Agent spawning, skill CRUD, no-duplicates enforcement
5. **Cron Manager & Memory** -- Parallel dispatch, multi-instance, WAL mode, memory lifecycle
6. **Work Release System** -- release-server.py, Web UI, auto-release rules, task state wiring
7. **Polish** -- Error recovery, health-check.py, docs, remaining toolkits, E2E testing
