# Dashboard Core Pages — Implementation Plan (Plan B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 4 core interactive pages — Requests, Tasks (list + detail with timeline/subtask tree), Agents (hierarchy + detail), and Releases (approval queue + rules) — all wired to the existing dashboard-server.py API endpoints.

**Architecture:** Each page is a React component in `src/pages/` consuming API data via `usePolling` hook. Shared types live in `src/types/`. Reusable utilities (timeAgo, status colors) extracted to `src/lib/format.ts`. All API endpoints already exist in dashboard-server.py — this plan is frontend-only. Additional shadcn components (tabs, textarea, collapsible, switch) installed as needed.

**Tech Stack:** React 18, TypeScript, Tailwind CSS v4, Shadcn/ui (New York style), React Router v7, lucide-react icons

---

## File Structure

```
dashboard/src/
├── types/
│   └── index.ts                          # Shared TypeScript interfaces
├── lib/
│   ├── api.ts                            # (exists) Fetch wrapper
│   ├── utils.ts                          # (exists) cn() utility
│   └── format.ts                         # NEW: timeAgo, statusColor, statusIcon helpers
├── hooks/
│   └── usePolling.ts                     # (exists) Generic polling hook
├── pages/
│   ├── OverviewPage.tsx                  # (exists)
│   ├── RequestsPage.tsx                  # NEW: Task 1
│   ├── TasksPage.tsx                     # NEW: Task 2
│   ├── TaskDetailPage.tsx                # NEW: Task 2
│   ├── AgentsPage.tsx                    # NEW: Task 3
│   ├── AgentDetailPage.tsx               # NEW: Task 3
│   └── ReleasesPage.tsx                  # NEW: Task 4
├── components/
│   ├── layout/ ...                       # (exists)
│   ├── overview/ ...                     # (exists)
│   ├── shared/
│   │   └── StatusBadge.tsx               # NEW: Reusable status badge component
│   ├── requests/
│   │   ├── RequestInput.tsx              # NEW: Task 1
│   │   └── RequestHistory.tsx            # NEW: Task 1
│   ├── tasks/
│   │   ├── TaskFilters.tsx               # NEW: Task 2
│   │   ├── TaskTable.tsx                 # NEW: Task 2
│   │   ├── TaskTimeline.tsx              # NEW: Task 2
│   │   └── SubtaskTree.tsx              # NEW: Task 2
│   ├── agents/
│   │   ├── AgentHierarchy.tsx            # NEW: Task 3
│   │   └── AgentStats.tsx               # NEW: Task 3
│   └── releases/
│       ├── ReleaseQueue.tsx              # NEW: Task 4
│       ├── ReleaseCard.tsx               # NEW: Task 4
│       └── AutoReleaseRules.tsx          # NEW: Task 4
│   └── ui/ ...                           # (exists) shadcn components
├── App.tsx                               # (modify) Wire new page routes
└── styles/globals.css                    # (exists)
```

---

## Task 1: Shared Types, Utilities, and Requests Page

**Files:**
- Create: `src/types/index.ts`
- Create: `src/lib/format.ts`
- Create: `src/components/shared/StatusBadge.tsx`
- Create: `src/components/requests/RequestInput.tsx`
- Create: `src/components/requests/RequestHistory.tsx`
- Create: `src/pages/RequestsPage.tsx`
- Modify: `src/App.tsx` (wire RequestsPage route)

### Step 1.1: Install shadcn textarea component

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent/dashboard"
npx shadcn@latest add textarea -y
```

Expected: `src/components/ui/textarea.tsx` created.

### Step 1.2: Create shared TypeScript interfaces

- [ ] Create `src/types/index.ts`:

```typescript
// ---- System ----

export interface StatusData {
  running_agents: number;
  total_agents: number;
  pending_tasks: number;
  assigned_tasks: number;
  pending_releases: number;
  active_rules: number;
  completed_today: number;
  success_rate: number;
  tasks_by_status: Record<string, number>;
}

// ---- Tasks ----

export type TaskStatus =
  | "pending"
  | "assigned"
  | "in_progress"
  | "awaiting_release"
  | "blocked"
  | "review"
  | "completed"
  | "failed"
  | "cancelled";

export interface TaskSummary {
  task_id: string;
  parent_task_id: string | null;
  title: string;
  status: TaskStatus;
  priority: number;
  assigned_agent: string | null;
  agent_name: string | null;
  created_by: string | null;
  framework: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface TaskDetail extends TaskSummary {
  description: string | null;
  toolkits_json: string | null;
  input_data: string | null;
  output_data: string | null;
  error_message: string | null;
  depends_on_json: string | null;
  updated_at: string | null;
  deadline: string | null;
  retry_count: number;
  max_retries: number;
}

export interface TaskListResponse {
  items: TaskSummary[];
  total: number;
}

export interface TimelineEvent {
  event_id: string;
  event_type: string;
  agent_id: string | null;
  agent_name: string | null;
  data_json: string;
  created_at: string;
}

export interface SubtaskNode {
  task_id: string;
  title: string;
  status: TaskStatus;
  assigned_agent: string | null;
  agent_name: string | null;
  priority: number;
  created_at: string;
  completed_at: string | null;
  children: SubtaskNode[];
}

// ---- Requests ----

export interface RequestItem {
  task_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: number;
  created_at: string;
  completed_at: string | null;
  output_data: string | null;
  subtask_count: number;
  completed_subtask_count: number;
}

export interface RequestListResponse {
  items: RequestItem[];
  total: number;
}

// ---- Agents ----

export interface AgentSummary {
  agent_id: string;
  agent_name: string;
  agent_type: string;
  level: number;
  parent_agent_id: string | null;
  status: string;
  run_count: number;
  error_count: number;
  last_run_at: string | null;
  active_task_count: number;
  success_rate: number;
}

export interface AgentDetail extends AgentSummary {
  prompt_file: string | null;
  skill_id: string | null;
  sub_agent_role: string | null;
  config_json: string | null;
  session_id: string | null;
  current_task: { task_id: string; title: string; status: string } | null;
  recent_tasks: TaskSummary[];
}

export interface AgentHierarchyNode extends AgentSummary {
  children: AgentHierarchyNode[];
}

export interface AgentSession {
  session_id: string;
  task_id: string | null;
  task_title: string | null;
  browser_category: string | null;
  status: string;
  success: number;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  summary: string | null;
}

// ---- Releases ----

export interface ReleaseItem {
  release_id: string;
  task_id: string;
  agent_id: string;
  agent_level: number;
  title: string;
  description: string | null;
  action_type: string;
  input_preview: string | null;
  output_preview: string | null;
  status: string;
  auto_release: number;
  auto_release_rule_id: string | null;
  reviewed_at: string | null;
  created_at: string;
  agent_name?: string;
  task_title?: string;
}

export interface ReleaseListResponse {
  items: ReleaseItem[];
  total: number;
}

export interface AutoReleaseRule {
  rule_id: string;
  match_agent_type: string | null;
  match_action_type: string | null;
  match_skill_id: string | null;
  match_title_pattern: string | null;
  is_enabled: number;
  created_from_release_id: string | null;
  fire_count: number;
  created_at: string;
}
```

### Step 1.3: Create formatting utilities

- [ ] Create `src/lib/format.ts`:

```typescript
export function timeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export type StatusVariant = "default" | "secondary" | "destructive" | "outline";

export function statusColor(status: string): string {
  switch (status) {
    case "completed":
    case "approved":
    case "auto_released":
      return "bg-green-500/15 text-green-400 border-green-500/30";
    case "in_progress":
    case "running":
      return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "pending":
    case "idle":
      return "bg-slate-500/15 text-slate-400 border-slate-500/30";
    case "assigned":
      return "bg-indigo-500/15 text-indigo-400 border-indigo-500/30";
    case "awaiting_release":
    case "review":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "blocked":
      return "bg-orange-500/15 text-orange-400 border-orange-500/30";
    case "failed":
    case "error":
    case "rejected":
      return "bg-red-500/15 text-red-400 border-red-500/30";
    case "cancelled":
      return "bg-gray-500/15 text-gray-500 border-gray-500/30";
    default:
      return "bg-slate-500/15 text-slate-400 border-slate-500/30";
  }
}

export function statusDot(status: string): string {
  switch (status) {
    case "completed":
    case "approved":
      return "bg-green-500";
    case "in_progress":
    case "running":
      return "bg-blue-500";
    case "pending":
    case "idle":
      return "bg-slate-400";
    case "assigned":
      return "bg-indigo-500";
    case "awaiting_release":
    case "review":
      return "bg-amber-500";
    case "failed":
    case "error":
      return "bg-red-500";
    case "blocked":
      return "bg-orange-500";
    default:
      return "bg-slate-400";
  }
}

export function priorityColor(priority: number): string {
  if (priority <= 2) return "text-red-400";
  if (priority <= 4) return "text-amber-400";
  if (priority <= 6) return "text-blue-400";
  return "text-slate-400";
}

export function actionTypeColor(actionType: string): string {
  switch (actionType) {
    case "plan":
      return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "research":
      return "bg-purple-500/15 text-purple-400 border-purple-500/30";
    case "design":
      return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
    case "execute":
      return "bg-green-500/15 text-green-400 border-green-500/30";
    case "review":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "store":
      return "bg-indigo-500/15 text-indigo-400 border-indigo-500/30";
    default:
      return "bg-slate-500/15 text-slate-400 border-slate-500/30";
  }
}
```

### Step 1.4: Create StatusBadge component

- [ ] Create `src/components/shared/StatusBadge.tsx`:

```tsx
import { Badge } from "@/components/ui/badge";
import { statusColor } from "@/lib/format";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const label = status.replace(/_/g, " ");
  return (
    <Badge
      variant="outline"
      className={`text-[10px] font-medium capitalize ${statusColor(status)} ${className}`}
    >
      {label}
    </Badge>
  );
}
```

### Step 1.5: Create RequestInput component

- [ ] Create `src/components/requests/RequestInput.tsx`:

```tsx
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Send, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface RequestInputProps {
  onSubmitted: () => void;
}

export function RequestInput({ onSubmitted }: RequestInputProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("5");
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;

    setSubmitting(true);
    setFeedback(null);

    try {
      const result = await api.post<{ ok: boolean; task_id: string }>("/api/requests", {
        title: title.trim(),
        description: description.trim() || null,
        priority: parseInt(priority, 10),
      });
      setFeedback({ ok: true, message: `Request submitted — Task ${result.task_id.slice(0, 8)}` });
      setTitle("");
      setDescription("");
      setPriority("5");
      onSubmitted();
    } catch (err) {
      setFeedback({ ok: false, message: err instanceof Error ? err.message : "Failed to submit" });
    } finally {
      setSubmitting(false);
      setTimeout(() => setFeedback(null), 4000);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">New Request</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input
            placeholder="What do you need done?"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={submitting}
          />
          <Textarea
            placeholder="Details (optional) — describe the task, constraints, expected outcome..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={submitting}
            rows={3}
            className="resize-none"
          />
          <div className="flex items-center gap-3">
            <Select value={priority} onValueChange={setPriority} disabled={submitting}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((p) => (
                  <SelectItem key={p} value={String(p)}>
                    P{p} {p <= 2 ? "— Critical" : p <= 4 ? "— High" : p <= 6 ? "— Medium" : "— Low"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button type="submit" disabled={submitting || !title.trim()} className="ml-auto">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Send className="h-4 w-4 mr-1" />}
              Submit
            </Button>
          </div>
          {feedback && (
            <p className={`text-xs ${feedback.ok ? "text-green-400" : "text-red-400"}`}>
              {feedback.message}
            </p>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
```

### Step 1.6: Create RequestHistory component

- [ ] Create `src/components/requests/RequestHistory.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, priorityColor } from "@/lib/format";
import type { RequestItem } from "@/types";

interface RequestHistoryProps {
  data: { items: RequestItem[]; total: number } | null;
}

export function RequestHistory({ data }: RequestHistoryProps) {
  const navigate = useNavigate();

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">
          Request History{data ? ` (${data.total})` : ""}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {!data && (
          <div className="px-4 pb-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 bg-muted rounded animate-pulse" />
            ))}
          </div>
        )}
        {data && data.items.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8 px-4">
            No requests yet — submit one above!
          </p>
        )}
        {data && data.items.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead className="w-28">Status</TableHead>
                <TableHead className="w-16 text-center">Priority</TableHead>
                <TableHead className="w-24">Created</TableHead>
                <TableHead className="w-24">Progress</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((item) => (
                <TableRow
                  key={item.task_id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => navigate(`/tasks/${item.task_id}`)}
                >
                  <TableCell className="font-medium text-sm">{item.title}</TableCell>
                  <TableCell><StatusBadge status={item.status} /></TableCell>
                  <TableCell className={`text-center font-mono text-sm ${priorityColor(item.priority)}`}>
                    {item.priority}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{timeAgo(item.created_at)}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {item.subtask_count > 0
                      ? `${item.completed_subtask_count}/${item.subtask_count}`
                      : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
```

### Step 1.7: Create RequestsPage

- [ ] Create `src/pages/RequestsPage.tsx`:

```tsx
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { RequestInput } from "@/components/requests/RequestInput";
import { RequestHistory } from "@/components/requests/RequestHistory";
import type { RequestListResponse } from "@/types";

export default function RequestsPage() {
  const { data, refresh } = usePolling<RequestListResponse>(
    () => api.get<RequestListResponse>("/api/requests?limit=50&offset=0"),
    5000
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Requests</h1>
        <p className="text-sm text-muted-foreground">Submit work to the Ultra Agent system</p>
      </div>
      <RequestInput onSubmitted={refresh} />
      <RequestHistory data={data} />
    </div>
  );
}
```

### Step 1.8: Wire RequestsPage into App.tsx

- [ ] In `src/App.tsx`, add the import and replace the Requests placeholder route:

Replace:
```typescript
import OverviewPage from "@/pages/OverviewPage";
```
With:
```typescript
import OverviewPage from "@/pages/OverviewPage";
import RequestsPage from "@/pages/RequestsPage";
```

Replace:
```tsx
<Route path="requests" element={<PlaceholderPage title="Requests" />} />
```
With:
```tsx
<Route path="requests" element={<RequestsPage />} />
```

### Step 1.9: Build and verify

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent/dashboard"
npm run build
```

Expected: Build succeeds with no TypeScript errors.

### Step 1.10: Commit

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add dashboard/src/
git commit -m "feat: add Requests page with input form and history table

Shared types (src/types/index.ts), formatting utilities (src/lib/format.ts),
and StatusBadge component reused across all pages.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Tasks Page (List + Detail with Timeline & Subtask Tree)

**Files:**
- Create: `src/components/tasks/TaskFilters.tsx`
- Create: `src/components/tasks/TaskTable.tsx`
- Create: `src/components/tasks/TaskTimeline.tsx`
- Create: `src/components/tasks/SubtaskTree.tsx`
- Create: `src/pages/TasksPage.tsx`
- Create: `src/pages/TaskDetailPage.tsx`
- Modify: `src/App.tsx` (wire TasksPage and TaskDetailPage routes)

### Step 2.1: Install shadcn collapsible component

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent/dashboard"
npx shadcn@latest add collapsible -y
```

Expected: `src/components/ui/collapsible.tsx` created.

### Step 2.2: Create TaskFilters component

- [ ] Create `src/components/tasks/TaskFilters.tsx`:

```tsx
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search } from "lucide-react";

interface TaskFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusChange: (value: string) => void;
  agentFilter: string;
  onAgentChange: (value: string) => void;
  agents: { agent_id: string; agent_name: string }[];
}

const STATUSES = [
  "all",
  "pending",
  "assigned",
  "in_progress",
  "awaiting_release",
  "blocked",
  "review",
  "completed",
  "failed",
  "cancelled",
];

export function TaskFilters({
  search,
  onSearchChange,
  statusFilter,
  onStatusChange,
  agentFilter,
  onAgentChange,
  agents,
}: TaskFiltersProps) {
  return (
    <div className="flex items-center gap-3">
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search tasks..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-8"
        />
      </div>
      <Select value={statusFilter} onValueChange={onStatusChange}>
        <SelectTrigger className="w-40">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          {STATUSES.map((s) => (
            <SelectItem key={s} value={s}>
              {s === "all" ? "All Statuses" : s.replace(/_/g, " ")}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={agentFilter} onValueChange={onAgentChange}>
        <SelectTrigger className="w-40">
          <SelectValue placeholder="Agent" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Agents</SelectItem>
          {agents.map((a) => (
            <SelectItem key={a.agent_id} value={a.agent_id}>
              {a.agent_name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
```

### Step 2.3: Create TaskTable component

- [ ] Create `src/components/tasks/TaskTable.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, formatDuration, priorityColor } from "@/lib/format";
import type { TaskSummary } from "@/types";

interface TaskTableProps {
  tasks: TaskSummary[];
  total: number;
}

export function TaskTable({ tasks, total }: TaskTableProps) {
  const navigate = useNavigate();

  if (tasks.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-12">
        No tasks match the current filters
      </p>
    );
  }

  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Title</TableHead>
            <TableHead className="w-28">Status</TableHead>
            <TableHead className="w-28">Agent</TableHead>
            <TableHead className="w-16 text-center">Priority</TableHead>
            <TableHead className="w-24">Created</TableHead>
            <TableHead className="w-20">Duration</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tasks.map((task) => (
            <TableRow
              key={task.task_id}
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => navigate(`/tasks/${task.task_id}`)}
            >
              <TableCell>
                <div className="flex items-center gap-2">
                  {task.parent_task_id && (
                    <span className="text-muted-foreground text-xs">↳</span>
                  )}
                  <span className="font-medium text-sm">{task.title}</span>
                </div>
              </TableCell>
              <TableCell><StatusBadge status={task.status} /></TableCell>
              <TableCell>
                {task.agent_name ? (
                  <Badge variant="outline" className="text-[10px] h-5 px-1.5">
                    {task.agent_name}
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className={`text-center font-mono text-sm ${priorityColor(task.priority)}`}>
                {task.priority}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {timeAgo(task.created_at)}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {formatDuration(task.duration_seconds)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground mt-2 px-2">
        Showing {tasks.length} of {total} tasks
      </p>
    </div>
  );
}
```

### Step 2.4: Create TaskTimeline component

- [ ] Create `src/components/tasks/TaskTimeline.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { timeAgo } from "@/lib/format";
import type { TimelineEvent } from "@/types";

interface TaskTimelineProps {
  events: TimelineEvent[] | null;
}

function eventIcon(eventType: string): string {
  if (eventType.includes("created")) return "●";
  if (eventType.includes("assigned")) return "→";
  if (eventType.includes("started") || eventType.includes("in_progress")) return "▶";
  if (eventType.includes("completed")) return "✓";
  if (eventType.includes("failed")) return "✗";
  if (eventType.includes("release") || eventType.includes("awaiting")) return "⏳";
  if (eventType.includes("subtask")) return "├";
  return "●";
}

function eventDotColor(eventType: string): string {
  if (eventType.includes("completed") || eventType.includes("approved")) return "bg-green-500";
  if (eventType.includes("failed") || eventType.includes("rejected") || eventType.includes("error")) return "bg-red-500";
  if (eventType.includes("assigned") || eventType.includes("started") || eventType.includes("in_progress")) return "bg-blue-500";
  if (eventType.includes("release") || eventType.includes("awaiting")) return "bg-amber-500";
  if (eventType.includes("subtask")) return "bg-indigo-500";
  return "bg-slate-500";
}

function formatEventType(eventType: string): string {
  return eventType.replace(/_/g, " ");
}

function parseEventData(dataJson: string): Record<string, unknown> {
  try {
    return JSON.parse(dataJson || "{}");
  } catch {
    return {};
  }
}

export function TaskTimeline({ events }: TaskTimelineProps) {
  const navigate = useNavigate();

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Execution Timeline</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="max-h-[500px] px-4 pb-4">
          {!events && (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex gap-3 animate-pulse">
                  <div className="h-2.5 w-2.5 rounded-full bg-muted mt-1.5" />
                  <div className="flex-1">
                    <div className="h-3 w-2/3 bg-muted rounded mb-1" />
                    <div className="h-2 w-1/3 bg-muted rounded" />
                  </div>
                </div>
              ))}
            </div>
          )}
          {events && events.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">No events recorded</p>
          )}
          {events && events.length > 0 && (
            <div className="space-y-0">
              {events.map((event, idx) => {
                const data = parseEventData(event.data_json);
                return (
                  <div key={event.event_id} className="flex gap-3 group">
                    <div className="flex flex-col items-center pt-1.5">
                      <div className={`h-2.5 w-2.5 rounded-full shrink-0 ${eventDotColor(event.event_type)}`} />
                      {idx < events.length - 1 && (
                        <div className="w-px flex-1 bg-border mt-1" />
                      )}
                    </div>
                    <div className="flex-1 pb-4">
                      <div className="flex items-center gap-2 mb-0.5">
                        {event.agent_name && (
                          <Badge
                            variant="outline"
                            className="text-[10px] h-4 px-1 cursor-pointer hover:bg-muted"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/agents/${event.agent_id}`);
                            }}
                          >
                            {event.agent_name}
                          </Badge>
                        )}
                        <span className="text-[10px] text-muted-foreground">
                          {timeAgo(event.created_at)}
                        </span>
                      </div>
                      <p className="text-xs text-foreground capitalize">
                        {eventIcon(event.event_type)} {formatEventType(event.event_type)}
                      </p>
                      {Object.keys(data).length > 0 && (
                        <div className="mt-1 p-2 bg-muted/50 rounded text-[10px] font-mono text-muted-foreground">
                          {Object.entries(data).map(([key, val]) => (
                            <div key={key}>
                              <span className="text-muted-foreground/70">{key}:</span>{" "}
                              {typeof val === "string" ? val : JSON.stringify(val)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
```

### Step 2.5: Create SubtaskTree component

- [ ] Create `src/components/tasks/SubtaskTree.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { SubtaskNode } from "@/types";

interface SubtaskTreeProps {
  subtasks: SubtaskNode[] | null;
}

function statusIcon(status: string): string {
  switch (status) {
    case "completed": return "✅";
    case "in_progress": return "⏳";
    case "pending": return "○";
    case "failed": return "❌";
    case "blocked": return "⏸";
    case "awaiting_release": return "🔒";
    case "cancelled": return "—";
    default: return "○";
  }
}

function TreeNode({ node, depth }: { node: SubtaskNode; depth: number }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-muted/50 cursor-pointer group"
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => navigate(`/tasks/${node.task_id}`)}
      >
        {hasChildren ? (
          <button
            className="h-4 w-4 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
          >
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}
        <span className="text-sm shrink-0">{statusIcon(node.status)}</span>
        <span className="text-sm text-foreground group-hover:text-primary transition-colors truncate flex-1">
          {node.title}
        </span>
        <StatusBadge status={node.status} />
        {node.agent_name && (
          <Badge variant="outline" className="text-[10px] h-4 px-1 shrink-0">
            {node.agent_name}
          </Badge>
        )}
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.task_id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function SubtaskTree({ subtasks }: SubtaskTreeProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Subtask Tree</CardTitle>
      </CardHeader>
      <CardContent className="p-0 pb-2">
        {!subtasks && (
          <div className="px-4 pb-2 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-8 bg-muted rounded animate-pulse" />
            ))}
          </div>
        )}
        {subtasks && subtasks.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">No subtasks</p>
        )}
        {subtasks && subtasks.length > 0 && (
          <div>
            {subtasks.map((node) => (
              <TreeNode key={node.task_id} node={node} depth={0} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

### Step 2.6: Create TasksPage

- [ ] Create `src/pages/TasksPage.tsx`:

```tsx
import { useState, useMemo, useCallback } from "react";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { TaskFilters } from "@/components/tasks/TaskFilters";
import { TaskTable } from "@/components/tasks/TaskTable";
import type { TaskListResponse, AgentSummary } from "@/types";

export default function TasksPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [agentFilter, setAgentFilter] = useState("all");

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", "100");
    params.set("offset", "0");
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (agentFilter !== "all") params.set("agent", agentFilter);
    if (search.trim()) params.set("search", search.trim());
    return params.toString();
  }, [search, statusFilter, agentFilter]);

  const fetcher = useCallback(
    () => api.get<TaskListResponse>(`/api/tasks?${queryString}`),
    [queryString]
  );

  const { data } = usePolling<TaskListResponse>(fetcher, 5000);

  const { data: agents } = usePolling<AgentSummary[]>(
    () => api.get<AgentSummary[]>("/api/agents"),
    30000
  );

  const agentOptions = useMemo(
    () => (agents || []).map((a) => ({ agent_id: a.agent_id, agent_name: a.agent_name })),
    [agents]
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Tasks</h1>
        <p className="text-sm text-muted-foreground">Browse and inspect all tasks in the system</p>
      </div>

      <TaskFilters
        search={search}
        onSearchChange={setSearch}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        agentFilter={agentFilter}
        onAgentChange={setAgentFilter}
        agents={agentOptions}
      />

      <Card>
        <CardContent className="p-0">
          {!data && (
            <div className="px-4 py-6 space-y-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-10 bg-muted rounded animate-pulse" />
              ))}
            </div>
          )}
          {data && <TaskTable tasks={data.items} total={data.total} />}
        </CardContent>
      </Card>
    </div>
  );
}
```

### Step 2.7: Create TaskDetailPage

- [ ] Create `src/pages/TaskDetailPage.tsx`:

```tsx
import { useParams, useNavigate } from "react-router-dom";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { TaskTimeline } from "@/components/tasks/TaskTimeline";
import { SubtaskTree } from "@/components/tasks/SubtaskTree";
import { ArrowLeft, Copy, Clock } from "lucide-react";
import { timeAgo, formatDuration, priorityColor } from "@/lib/format";
import type { TaskDetail, TimelineEvent, SubtaskNode } from "@/types";

function JsonPanel({ title, data }: { title: string; data: string | null }) {
  if (!data) return null;

  let formatted: string;
  try {
    formatted = JSON.stringify(JSON.parse(data), null, 2);
  } catch {
    formatted = data;
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2"
            onClick={() => navigator.clipboard.writeText(formatted)}
          >
            <Copy className="h-3 w-3" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <pre className="text-[11px] font-mono bg-muted/50 p-3 rounded overflow-auto max-h-60">
          {formatted}
        </pre>
      </CardContent>
    </Card>
  );
}

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: task } = usePolling<TaskDetail>(
    () => api.get<TaskDetail>(`/api/tasks/${id}`),
    5000
  );

  const { data: timeline } = usePolling<TimelineEvent[]>(
    () => api.get<TimelineEvent[]>(`/api/tasks/${id}/timeline`),
    5000
  );

  const { data: subtasks } = usePolling<SubtaskNode[]>(
    () => api.get<SubtaskNode[]>(`/api/tasks/${id}/subtasks`),
    5000
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Button
          variant="ghost"
          size="sm"
          className="mb-2 -ml-2 text-muted-foreground"
          onClick={() => navigate("/tasks")}
        >
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Tasks
        </Button>

        {!task && (
          <div className="space-y-2 animate-pulse">
            <div className="h-7 w-2/3 bg-muted rounded" />
            <div className="h-4 w-1/3 bg-muted rounded" />
          </div>
        )}

        {task && (
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{task.title}</h1>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span className="font-mono">{task.task_id.slice(0, 8)}</span>
                <span className={`font-mono ${priorityColor(task.priority)}`}>P{task.priority}</span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" /> {timeAgo(task.created_at)}
                </span>
                {task.duration_seconds !== null && (
                  <span>Duration: {formatDuration(task.duration_seconds)}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={task.status} />
              {task.agent_name && (
                <Badge
                  variant="outline"
                  className="cursor-pointer hover:bg-muted"
                  onClick={() => navigate(`/agents/${task.assigned_agent}`)}
                >
                  {task.agent_name}
                </Badge>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Error Banner */}
      {task?.status === "failed" && task.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
          <p className="text-sm font-medium text-red-400">Error</p>
          <p className="text-xs text-red-400/80 mt-1">{task.error_message}</p>
        </div>
      )}

      {/* Description */}
      {task?.description && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">{task.description}</p>
          </CardContent>
        </Card>
      )}

      {/* Timeline + Subtask Tree */}
      <div className="grid grid-cols-5 gap-4">
        <div className="col-span-3">
          <TaskTimeline events={timeline} />
        </div>
        <div className="col-span-2">
          <SubtaskTree subtasks={subtasks} />
        </div>
      </div>

      {/* Input / Output Data */}
      <div className="grid grid-cols-2 gap-4">
        <JsonPanel title="Input Data" data={task?.input_data ?? null} />
        <JsonPanel title="Output Data" data={task?.output_data ?? null} />
      </div>
    </div>
  );
}
```

### Step 2.8: Wire TasksPage and TaskDetailPage into App.tsx

- [ ] In `src/App.tsx`, add imports:

```typescript
import TasksPage from "@/pages/TasksPage";
import TaskDetailPage from "@/pages/TaskDetailPage";
```

Replace:
```tsx
<Route path="tasks" element={<PlaceholderPage title="Tasks" />} />
<Route path="tasks/:id" element={<PlaceholderPage title="Task Detail" />} />
```
With:
```tsx
<Route path="tasks" element={<TasksPage />} />
<Route path="tasks/:id" element={<TaskDetailPage />} />
```

### Step 2.9: Build and verify

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent/dashboard"
npm run build
```

Expected: Build succeeds.

### Step 2.10: Commit

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add dashboard/src/
git commit -m "feat: add Tasks page with filters, detail view, timeline, and subtask tree

Task list with status/agent/search filters. Task detail shows execution
timeline (who did what, when) and recursive subtask tree with expand/collapse.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Agents Page (Hierarchy + Detail)

**Files:**
- Create: `src/components/agents/AgentHierarchy.tsx`
- Create: `src/components/agents/AgentStats.tsx`
- Create: `src/pages/AgentsPage.tsx`
- Create: `src/pages/AgentDetailPage.tsx`
- Modify: `src/App.tsx` (wire agent routes)

### Step 3.1: Create AgentHierarchy component

- [ ] Create `src/components/agents/AgentHierarchy.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { statusDot } from "@/lib/format";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { AgentHierarchyNode } from "@/types";

interface AgentHierarchyProps {
  data: AgentHierarchyNode | null;
}

function HierarchyNode({ node, depth }: { node: AgentHierarchyNode; depth: number }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-2.5 py-2 px-3 rounded-md hover:bg-muted/50 cursor-pointer group transition-colors"
        style={{ paddingLeft: `${depth * 24 + 12}px` }}
        onClick={() => navigate(`/agents/${node.agent_id}`)}
      >
        {hasChildren ? (
          <button
            className="h-4 w-4 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
          >
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}

        {/* Status dot */}
        <div className="relative shrink-0">
          <div className={`h-2.5 w-2.5 rounded-full ${statusDot(node.status)}`} />
          {node.status === "running" && (
            <div className={`absolute inset-0 h-2.5 w-2.5 rounded-full ${statusDot(node.status)} animate-ping opacity-50`} />
          )}
        </div>

        {/* Name + type */}
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">
            {node.agent_name}
          </span>
          <span className="text-[10px] text-muted-foreground ml-2">
            {node.agent_type}
          </span>
        </div>

        {/* Level badge */}
        <Badge variant="outline" className="text-[10px] h-4 px-1 shrink-0">
          L{node.level}
        </Badge>

        {/* Stats */}
        <span className="text-[10px] text-muted-foreground shrink-0">
          {node.run_count} runs
          {node.error_count > 0 && (
            <span className="text-red-400 ml-1">/ {node.error_count} err</span>
          )}
        </span>
      </div>

      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <HierarchyNode key={child.agent_id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function AgentHierarchy({ data }: AgentHierarchyProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Agent Hierarchy</CardTitle>
      </CardHeader>
      <CardContent className="p-0 pb-2">
        {!data && (
          <div className="px-4 pb-2 space-y-2">
            {[1, 2, 3, 4, 5, 6, 7].map((i) => (
              <div key={i} className="h-9 bg-muted rounded animate-pulse" style={{ marginLeft: `${(i % 3) * 24}px` }} />
            ))}
          </div>
        )}
        {data && <HierarchyNode node={data} depth={0} />}
      </CardContent>
    </Card>
  );
}
```

### Step 3.2: Create AgentStats component

- [ ] Create `src/components/agents/AgentStats.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, formatDuration } from "@/lib/format";
import type { AgentDetail } from "@/types";

interface AgentStatsProps {
  agent: AgentDetail;
}

export function AgentStats({ agent }: AgentStatsProps) {
  const navigate = useNavigate();

  return (
    <div className="space-y-4">
      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <p className="text-2xl font-bold text-foreground">{agent.run_count}</p>
            <p className="text-xs text-muted-foreground">Total Runs</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <p className="text-2xl font-bold text-red-400">{agent.error_count}</p>
            <p className="text-xs text-muted-foreground">Errors</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <p className="text-2xl font-bold text-green-400">
              {Math.round(agent.success_rate * 100)}%
            </p>
            <p className="text-xs text-muted-foreground">Success Rate</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <p className="text-lg font-bold text-foreground">
              {agent.last_run_at ? timeAgo(agent.last_run_at) : "Never"}
            </p>
            <p className="text-xs text-muted-foreground">Last Run</p>
          </CardContent>
        </Card>
      </div>

      {/* Current Task */}
      {agent.current_task && (
        <Card className="border-blue-500/30">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-blue-400">Current Task</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="flex items-center justify-between cursor-pointer hover:opacity-80"
              onClick={() => navigate(`/tasks/${agent.current_task!.task_id}`)}
            >
              <span className="text-sm font-medium">{agent.current_task.title}</span>
              <StatusBadge status={agent.current_task.status} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Tasks */}
      {agent.recent_tasks && agent.recent_tasks.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Recent Tasks</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead className="w-24">Status</TableHead>
                  <TableHead className="w-20">Duration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {agent.recent_tasks.map((task) => (
                  <TableRow
                    key={task.task_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/tasks/${task.task_id}`)}
                  >
                    <TableCell className="text-sm">{task.title}</TableCell>
                    <TableCell><StatusBadge status={task.status} /></TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDuration(task.duration_seconds)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

### Step 3.3: Create AgentsPage

- [ ] Create `src/pages/AgentsPage.tsx`:

```tsx
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { AgentHierarchy } from "@/components/agents/AgentHierarchy";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";
import { statusDot, timeAgo } from "@/lib/format";
import type { AgentHierarchyNode, AgentSummary } from "@/types";

export default function AgentsPage() {
  const navigate = useNavigate();

  const { data: hierarchy } = usePolling<AgentHierarchyNode>(
    () => api.get<AgentHierarchyNode>("/api/agents/hierarchy"),
    5000
  );

  const { data: agents } = usePolling<AgentSummary[]>(
    () => api.get<AgentSummary[]>("/api/agents"),
    5000
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Agents</h1>
        <p className="text-sm text-muted-foreground">4-level agent hierarchy — Director → Agents → Sub-Agents → Workers</p>
      </div>

      <AgentHierarchy data={hierarchy} />

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">All Agents</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!agents && (
            <div className="px-4 pb-4 space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-10 bg-muted rounded animate-pulse" />
              ))}
            </div>
          )}
          {agents && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead className="w-16">Level</TableHead>
                  <TableHead className="w-20">Status</TableHead>
                  <TableHead className="w-20 text-center">Runs</TableHead>
                  <TableHead className="w-20 text-center">Errors</TableHead>
                  <TableHead className="w-24 text-center">Success</TableHead>
                  <TableHead className="w-24">Last Run</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {agents.map((agent) => (
                  <TableRow
                    key={agent.agent_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/agents/${agent.agent_id}`)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className={`h-2 w-2 rounded-full ${statusDot(agent.status)}`} />
                        <span className="font-medium text-sm">{agent.agent_name}</span>
                        <span className="text-[10px] text-muted-foreground">{agent.agent_type}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px] h-4 px-1">L{agent.level}</Badge>
                    </TableCell>
                    <TableCell className="capitalize text-xs">{agent.status}</TableCell>
                    <TableCell className="text-center text-sm">{agent.run_count}</TableCell>
                    <TableCell className="text-center text-sm">
                      <span className={agent.error_count > 0 ? "text-red-400" : "text-muted-foreground"}>
                        {agent.error_count}
                      </span>
                    </TableCell>
                    <TableCell className="text-center text-sm">
                      {Math.round(agent.success_rate * 100)}%
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {agent.last_run_at ? timeAgo(agent.last_run_at) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

### Step 3.4: Create AgentDetailPage

- [ ] Create `src/pages/AgentDetailPage.tsx`:

```tsx
import { useParams, useNavigate } from "react-router-dom";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft } from "lucide-react";
import { statusDot, timeAgo } from "@/lib/format";
import { AgentStats } from "@/components/agents/AgentStats";
import type { AgentDetail } from "@/types";

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: agent } = usePolling<AgentDetail>(
    () => api.get<AgentDetail>(`/api/agents/${id}`),
    5000
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Button
          variant="ghost"
          size="sm"
          className="mb-2 -ml-2 text-muted-foreground"
          onClick={() => navigate("/agents")}
        >
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Agents
        </Button>

        {!agent && (
          <div className="space-y-2 animate-pulse">
            <div className="h-7 w-1/2 bg-muted rounded" />
            <div className="h-4 w-1/4 bg-muted rounded" />
          </div>
        )}

        {agent && (
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className={`h-3 w-3 rounded-full ${statusDot(agent.status)}`} />
                  {agent.status === "running" && (
                    <div className={`absolute inset-0 h-3 w-3 rounded-full ${statusDot(agent.status)} animate-ping opacity-50`} />
                  )}
                </div>
                <h1 className="text-2xl font-bold text-foreground">{agent.agent_name}</h1>
              </div>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span className="capitalize">{agent.agent_type}</span>
                <Badge variant="outline" className="text-[10px] h-4 px-1">L{agent.level}</Badge>
                {agent.parent_agent_id && (
                  <span
                    className="cursor-pointer hover:text-primary"
                    onClick={() => navigate(`/agents/${agent.parent_agent_id}`)}
                  >
                    Parent: {agent.parent_agent_id}
                  </span>
                )}
                {agent.last_run_at && <span>Last active: {timeAgo(agent.last_run_at)}</span>}
              </div>
            </div>
            <Badge
              variant="outline"
              className={`capitalize ${agent.status === "running" ? "border-blue-500/30 text-blue-400" : agent.status === "error" ? "border-red-500/30 text-red-400" : ""}`}
            >
              {agent.status}
            </Badge>
          </div>
        )}
      </div>

      {/* Stats + Recent Tasks */}
      {agent && <AgentStats agent={agent} />}
    </div>
  );
}
```

### Step 3.5: Wire AgentsPage and AgentDetailPage into App.tsx

- [ ] In `src/App.tsx`, add imports:

```typescript
import AgentsPage from "@/pages/AgentsPage";
import AgentDetailPage from "@/pages/AgentDetailPage";
```

Replace:
```tsx
<Route path="agents" element={<PlaceholderPage title="Agents" />} />
<Route path="agents/:id" element={<PlaceholderPage title="Agent Detail" />} />
```
With:
```tsx
<Route path="agents" element={<AgentsPage />} />
<Route path="agents/:id" element={<AgentDetailPage />} />
```

### Step 3.6: Build and verify

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent/dashboard"
npm run build
```

Expected: Build succeeds.

### Step 3.7: Commit

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add dashboard/src/
git commit -m "feat: add Agents page with hierarchy tree and detail view

Tree visualization of Director → L1 → L2 → L3 with status dots and
pulsing animations for running agents. Detail view shows stats, current
task, and recent task history.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Releases Page (Approval Queue + Auto-Release Rules)

**Files:**
- Create: `src/components/releases/ReleaseCard.tsx`
- Create: `src/components/releases/ReleaseQueue.tsx`
- Create: `src/components/releases/AutoReleaseRules.tsx`
- Create: `src/pages/ReleasesPage.tsx`
- Modify: `src/App.tsx` (wire ReleasesPage route)

### Step 4.1: Create ReleaseCard component

- [ ] Create `src/components/releases/ReleaseCard.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Check, X, Zap, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { timeAgo, actionTypeColor } from "@/lib/format";
import type { ReleaseItem } from "@/types";

interface ReleaseCardProps {
  release: ReleaseItem;
  onAction: () => void;
}

export function ReleaseCard({ release, onAction }: ReleaseCardProps) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<string | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  async function handleApprove() {
    setLoading("approve");
    try {
      await api.post(`/api/releases/${release.release_id}/approve`);
      onAction();
    } finally {
      setLoading(null);
    }
  }

  async function handleReject() {
    setLoading("reject");
    try {
      await api.post(`/api/releases/${release.release_id}/reject`, {
        reason: rejectReason || undefined,
      });
      setRejectOpen(false);
      setRejectReason("");
      onAction();
    } finally {
      setLoading(null);
    }
  }

  async function handleAutoRelease() {
    setLoading("auto");
    try {
      await api.post(`/api/releases/${release.release_id}/auto-release`);
      onAction();
    } finally {
      setLoading(null);
    }
  }

  return (
    <>
      <Card className="border-amber-500/20">
        <CardContent className="pt-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-medium text-foreground truncate">{release.title}</h3>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className="text-[10px] h-4 px-1">
                  {release.agent_name || release.agent_id} (L{release.agent_level})
                </Badge>
                <Badge variant="outline" className={`text-[10px] h-4 px-1 ${actionTypeColor(release.action_type)}`}>
                  {release.action_type}
                </Badge>
                <span className="text-[10px] text-muted-foreground">{timeAgo(release.created_at)}</span>
              </div>
            </div>
          </div>

          {release.description && (
            <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{release.description}</p>
          )}

          {release.input_preview && (
            <pre className="text-[10px] font-mono bg-muted/50 p-2 rounded mb-3 overflow-hidden max-h-20 text-muted-foreground">
              {release.input_preview}
            </pre>
          )}

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              className="h-7 text-xs bg-green-600 hover:bg-green-700"
              onClick={handleApprove}
              disabled={loading !== null}
            >
              {loading === "approve" ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Check className="h-3 w-3 mr-1" />}
              Approve
            </Button>
            <Button
              size="sm"
              variant="destructive"
              className="h-7 text-xs"
              onClick={() => setRejectOpen(true)}
              disabled={loading !== null}
            >
              <X className="h-3 w-3 mr-1" /> Reject
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs border-purple-500/30 text-purple-400 hover:bg-purple-500/10"
              onClick={handleAutoRelease}
              disabled={loading !== null}
            >
              {loading === "auto" ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Zap className="h-3 w-3 mr-1" />}
              Auto-Release
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs ml-auto text-muted-foreground"
              onClick={() => navigate(`/tasks/${release.task_id}`)}
            >
              View Task →
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Release</DialogTitle>
          </DialogHeader>
          <Textarea
            placeholder="Reason for rejection (optional)"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={3}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRejectOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleReject} disabled={loading === "reject"}>
              {loading === "reject" ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
```

### Step 4.2: Create ReleaseQueue component

- [ ] Create `src/components/releases/ReleaseQueue.tsx`:

```tsx
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ReleaseCard } from "./ReleaseCard";
import { CheckCheck, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { ReleaseItem } from "@/types";

interface ReleaseQueueProps {
  releases: ReleaseItem[];
  onAction: () => void;
}

export function ReleaseQueue({ releases, onAction }: ReleaseQueueProps) {
  const [approvingAll, setApprovingAll] = useState(false);

  const pending = releases.filter((r) => r.status === "pending");

  async function handleApproveAll() {
    setApprovingAll(true);
    try {
      for (const release of pending) {
        await api.post(`/api/releases/${release.release_id}/approve`);
      }
      onAction();
    } finally {
      setApprovingAll(false);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">
            Pending Releases ({pending.length})
          </CardTitle>
          {pending.length > 1 && (
            <Button
              size="sm"
              className="h-7 text-xs bg-green-600 hover:bg-green-700"
              onClick={handleApproveAll}
              disabled={approvingAll}
            >
              {approvingAll ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : (
                <CheckCheck className="h-3 w-3 mr-1" />
              )}
              Approve All ({pending.length})
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {pending.length === 0 && (
          <div className="text-center py-8">
            <div className="text-3xl mb-2">✓</div>
            <p className="text-sm text-muted-foreground">No pending releases — all clear!</p>
          </div>
        )}
        {pending.length > 0 && (
          <div className="space-y-3">
            {pending.map((release) => (
              <ReleaseCard key={release.release_id} release={release} onAction={onAction} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

### Step 4.3: Create AutoReleaseRules component

- [ ] Create `src/components/releases/AutoReleaseRules.tsx`:

```tsx
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { AutoReleaseRule } from "@/types";

interface AutoReleaseRulesProps {
  rules: AutoReleaseRule[] | null;
  onAction: () => void;
}

export function AutoReleaseRules({ rules, onAction }: AutoReleaseRulesProps) {
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  async function handleDelete(ruleId: string) {
    await api.delete(`/api/rules/${ruleId}`);
    setDeleteTarget(null);
    onAction();
  }

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">
            Auto-Release Rules{rules ? ` (${rules.length})` : ""}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!rules && (
            <div className="px-4 pb-4 space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-10 bg-muted rounded animate-pulse" />
              ))}
            </div>
          )}
          {rules && rules.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-6">
              No auto-release rules yet. Click "Auto-Release" on a pending release to create one.
            </p>
          )}
          {rules && rules.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent Type</TableHead>
                  <TableHead>Action Type</TableHead>
                  <TableHead>Title Pattern</TableHead>
                  <TableHead className="w-16 text-center">Fires</TableHead>
                  <TableHead className="w-16">Status</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => (
                  <TableRow key={rule.rule_id}>
                    <TableCell className="text-sm">{rule.match_agent_type || "*"}</TableCell>
                    <TableCell className="text-sm">{rule.match_action_type || "*"}</TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">
                      {rule.match_title_pattern || "—"}
                    </TableCell>
                    <TableCell className="text-center text-sm">{rule.fire_count}</TableCell>
                    <TableCell>
                      <span className={`text-xs ${rule.is_enabled ? "text-green-400" : "text-muted-foreground"}`}>
                        {rule.is_enabled ? "Active" : "Disabled"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0 text-muted-foreground hover:text-red-400"
                        onClick={() => setDeleteTarget(rule.rule_id)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={deleteTarget !== null} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Rule</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Delete this auto-release rule? Future matching releases will require manual approval.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={() => deleteTarget && handleDelete(deleteTarget)}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
```

### Step 4.4: Create ReleasesPage

- [ ] Create `src/pages/ReleasesPage.tsx`:

```tsx
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { ReleaseQueue } from "@/components/releases/ReleaseQueue";
import { AutoReleaseRules } from "@/components/releases/AutoReleaseRules";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo } from "@/lib/format";
import type { ReleaseItem, ReleaseListResponse, AutoReleaseRule } from "@/types";

export default function ReleasesPage() {
  const { data: pendingData, refresh: refreshPending } = usePolling<ReleaseListResponse>(
    () => api.get<ReleaseListResponse>("/api/releases?status=pending"),
    5000
  );

  const { data: recentData, refresh: refreshRecent } = usePolling<ReleaseListResponse>(
    () => api.get<ReleaseListResponse>("/api/releases?limit=20"),
    5000
  );

  const { data: rules, refresh: refreshRules } = usePolling<AutoReleaseRule[]>(
    () => api.get<AutoReleaseRule[]>("/api/rules"),
    10000
  );

  function handleAction() {
    refreshPending();
    refreshRecent();
    refreshRules();
  }

  const recentReviewed = (recentData?.items || []).filter(
    (r) => r.status !== "pending"
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Work Releases</h1>
        <p className="text-sm text-muted-foreground">Review and approve agent work before execution</p>
      </div>

      <ReleaseQueue
        releases={pendingData?.items || []}
        onAction={handleAction}
      />

      <AutoReleaseRules rules={rules} onAction={handleAction} />

      {/* Recent History */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Recent History</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {recentReviewed.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-6">No reviewed releases yet</p>
          )}
          {recentReviewed.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead className="w-24">Agent</TableHead>
                  <TableHead className="w-24">Status</TableHead>
                  <TableHead className="w-24">Reviewed</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentReviewed.map((release) => (
                  <TableRow key={release.release_id}>
                    <TableCell className="text-sm">{release.title}</TableCell>
                    <TableCell className="text-xs">{release.agent_name || release.agent_id}</TableCell>
                    <TableCell><StatusBadge status={release.status} /></TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {release.reviewed_at ? timeAgo(release.reviewed_at) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

### Step 4.5: Wire ReleasesPage into App.tsx

- [ ] In `src/App.tsx`, add import:

```typescript
import ReleasesPage from "@/pages/ReleasesPage";
```

Replace:
```tsx
<Route path="releases" element={<PlaceholderPage title="Work Releases" />} />
```
With:
```tsx
<Route path="releases" element={<ReleasesPage />} />
```

### Step 4.6: Build and verify

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent/dashboard"
npm run build
```

Expected: Build succeeds.

### Step 4.7: Commit

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add dashboard/src/
git commit -m "feat: add Releases page with approval queue, auto-release rules, and history

Pending releases shown as cards with Approve/Reject/Auto-Release actions.
Reject opens dialog for optional reason. Auto-release creates reusable rule.
Rules table with delete. Recent history table for reviewed releases.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Final Build and Production Update

**Files:**
- Modify: `dashboard/dist/` (rebuild)

### Step 5.1: Production build

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent/dashboard"
npm run build
```

Expected: Build succeeds.

### Step 5.2: Commit production build

- [ ] Run:

```bash
cd "C:/Users/jfcho/Desktop/CoWork/MultiAgent"
git add dashboard/dist/
git commit -m "build: update production bundle with all core pages

Includes Requests, Tasks (list + detail), Agents (hierarchy + detail),
and Releases (queue + rules) pages.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Summary

After completing all 5 tasks, the dashboard will have:

1. **Requests page** — Input form with priority selector, submission feedback, paginated history table
2. **Tasks page** — Filterable task list (status/agent/search), task detail with execution timeline and recursive subtask tree, input/output JSON panels
3. **Agents page** — Hierarchical tree visualization (L0→L3) with status dots and pulsing animations, detail view with stats cards, current task, recent task history
4. **Releases page** — Pending release cards with Approve/Reject/Auto-Release actions, auto-release rules management, recent history table
5. **Shared infrastructure** — TypeScript interfaces (`types/`), formatting utilities (`format.ts`), reusable StatusBadge component

All pages poll at 5-second intervals and connect to the existing dashboard-server.py API endpoints. Plan C (Skills, Sessions, Improvements, Settings) can build on this foundation.
