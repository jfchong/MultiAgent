# Dashboard Advanced Pages — Implementation Plan (Plan C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 4 remaining dashboard pages — Skills (list + detail with invocations), Sessions (list + detail with step recordings), Improvements (log + stats), and Settings (config editor + credentials + cron management).

**Architecture:** Same as Plan B — each page consumes existing dashboard-server.py API endpoints via `usePolling`. New types added to `src/types/index.ts`. Shared utilities from `src/lib/format.ts`. Additional shadcn components (tabs, switch) installed as needed.

**Tech Stack:** React 18, TypeScript, Tailwind CSS v4, Shadcn/ui (New York style), React Router v7, lucide-react icons

---

## Task 1: Skills Page (List + Detail with Invocations)

**Files:**
- Modify: `src/types/index.ts` (add Skills + Sessions + Improvements + Settings types)
- Create: `src/components/skills/SkillTable.tsx`
- Create: `src/components/skills/SkillInvocations.tsx`
- Create: `src/pages/SkillsPage.tsx`
- Create: `src/pages/SkillDetailPage.tsx`
- Modify: `src/App.tsx`

### Step 1.1: Add remaining types to `src/types/index.ts`

- [ ] Append the following types:

```typescript
// ---- Skills ----

export interface SkillSummary {
  skill_id: string;
  skill_name: string;
  namespace: string;
  category: string;
  description: string;
  success_count: number | null;
  failure_count: number | null;
  version: number;
  is_active: number;
  last_used_at: string | null;
  created_at: string;
  success_rate: number;
}

export interface SkillDetail extends SkillSummary {
  agent_template: string;
  data_schema: unknown;
  output_schema: unknown;
  tools_required: string[] | unknown;
  updated_at: string;
}

export interface SkillListResponse {
  items: SkillSummary[];
  total: number;
}

export interface SkillInvocation {
  invocation_id: string;
  task_id: string;
  agent_id: string;
  input_data: string;
  output_data: string | null;
  status: string;
  duration_seconds: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface SkillInvocationListResponse {
  items: SkillInvocation[];
  total: number;
}

// ---- Sessions ----

export interface SessionSummary {
  session_id: string;
  agent_id: string;
  agent_name: string | null;
  task_id: string;
  task_title: string | null;
  browser_category: string | null;
  status: string;
  success: number | null;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  summary: string | null;
}

export interface SessionDetail extends SessionSummary {
  parent_session_id: string | null;
  output_snapshot: string | null;
  error_message: string | null;
  created_at: string;
  recordings: SessionRecording[];
}

export interface SessionListResponse {
  items: SessionSummary[];
  total: number;
}

export interface SessionRecording {
  recording_id: string;
  session_id: string;
  step_number: number;
  action_type: string;
  target: string | null;
  value: string | null;
  result: string | null;
  timestamp: string;
  duration_ms: number | null;
}

// ---- Improvements ----

export interface ImprovementItem {
  log_id: string;
  task_id: string | null;
  task_title: string | null;
  agent_id: string | null;
  agent_name: string | null;
  category: string;
  summary: string;
  details: string | null;
  impact_score: number | null;
  action_taken: string | null;
  created_at: string;
}

export interface ImprovementListResponse {
  items: ImprovementItem[];
  total: number;
}

export interface ImprovementStats {
  total_patterns: number;
  avg_impact_score: number;
  by_category: Record<string, { count: number; avg_impact: number }>;
  top_improving_agents: Array<{
    agent_id: string | null;
    agent_name: string | null;
    count: number;
    avg_impact: number;
  }>;
}

// ---- Settings ----

export interface ConfigItem {
  key: string;
  value: string;
}

export interface CredentialItem {
  credential_id: string;
  site_domain: string;
  label: string;
  auth_type: string;
  created_at: string;
  updated_at: string;
}

export interface CronJob {
  schedule_id: string;
  agent_id: string;
  agent_name: string | null;
  cron_expression: string;
  task_template: string | null;
  is_enabled: number;
  last_fired_at: string | null;
  next_fire_at: string | null;
  fire_count: number;
  max_fires: number | null;
  created_at: string;
}
```

### Step 1.2: Create SkillTable component

- [ ] Create `src/components/skills/SkillTable.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { timeAgo } from "@/lib/format";
import type { SkillSummary } from "@/types";

interface SkillTableProps { skills: SkillSummary[]; total: number; }

export function SkillTable({ skills, total }: SkillTableProps) {
  const navigate = useNavigate();
  if (skills.length === 0) return <p className="text-sm text-muted-foreground text-center py-12">No skills found</p>;
  return (
    <div>
      <Table>
        <TableHeader><TableRow>
          <TableHead>Name</TableHead>
          <TableHead className="w-24">Category</TableHead>
          <TableHead className="w-20">Version</TableHead>
          <TableHead className="w-20 text-center">Success</TableHead>
          <TableHead className="w-20 text-center">Failure</TableHead>
          <TableHead className="w-20 text-center">Rate</TableHead>
          <TableHead className="w-20">Status</TableHead>
          <TableHead className="w-24">Last Used</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {skills.map((skill) => (
            <TableRow key={skill.skill_id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/skills/${skill.skill_id}`)}>
              <TableCell>
                <div>
                  <span className="font-medium text-sm">{skill.skill_name}</span>
                  <p className="text-[10px] text-muted-foreground truncate max-w-xs">{skill.description}</p>
                </div>
              </TableCell>
              <TableCell><Badge variant="outline" className="text-[10px] h-4 px-1">{skill.category}</Badge></TableCell>
              <TableCell className="text-sm text-center">v{skill.version}</TableCell>
              <TableCell className="text-center text-sm text-green-400">{skill.success_count ?? 0}</TableCell>
              <TableCell className="text-center text-sm text-red-400">{skill.failure_count ?? 0}</TableCell>
              <TableCell className="text-center text-sm">{Math.round(skill.success_rate * 100)}%</TableCell>
              <TableCell>
                <span className={`text-xs ${skill.is_active ? "text-green-400" : "text-muted-foreground"}`}>
                  {skill.is_active ? "Active" : "Inactive"}
                </span>
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">{skill.last_used_at ? timeAgo(skill.last_used_at) : "Never"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground mt-2 px-2">Showing {skills.length} of {total} skills</p>
    </div>
  );
}
```

### Step 1.3: Create SkillInvocations component

- [ ] Create `src/components/skills/SkillInvocations.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, formatDuration } from "@/lib/format";
import type { SkillInvocationListResponse } from "@/types";

interface SkillInvocationsProps { data: SkillInvocationListResponse | null; }

export function SkillInvocations({ data }: SkillInvocationsProps) {
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Invocation History{data ? ` (${data.total})` : ""}</CardTitle></CardHeader>
      <CardContent className="p-0">
        {!data && <div className="px-4 pb-4 space-y-2">{[1,2,3].map((i) => <div key={i} className="h-10 bg-muted rounded animate-pulse" />)}</div>}
        {data && data.items.length === 0 && <p className="text-sm text-muted-foreground text-center py-6">No invocations yet</p>}
        {data && data.items.length > 0 && (
          <Table>
            <TableHeader><TableRow>
              <TableHead>Agent</TableHead>
              <TableHead className="w-24">Status</TableHead>
              <TableHead className="w-20">Duration</TableHead>
              <TableHead className="w-24">When</TableHead>
              <TableHead>Error</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.items.map((inv) => (
                <TableRow key={inv.invocation_id}>
                  <TableCell className="text-sm font-mono">{inv.agent_id}</TableCell>
                  <TableCell><StatusBadge status={inv.status} /></TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatDuration(inv.duration_seconds)}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{timeAgo(inv.created_at)}</TableCell>
                  <TableCell className="text-xs text-red-400 truncate max-w-xs">{inv.error_message || "—"}</TableCell>
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

### Step 1.4: Create SkillsPage

- [ ] Create `src/pages/SkillsPage.tsx`:

```tsx
import { useState, useMemo, useCallback } from "react";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SkillTable } from "@/components/skills/SkillTable";
import { Search } from "lucide-react";
import type { SkillListResponse } from "@/types";

export default function SkillsPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", "100");
    if (search.trim()) params.set("search", search.trim());
    if (category !== "all") params.set("category", category);
    return params.toString();
  }, [search, category]);

  const fetcher = useCallback(() => api.get<SkillListResponse>(`/api/skills?${queryString}`), [queryString]);
  const { data } = usePolling<SkillListResponse>(fetcher, 5000);

  const categories = useMemo(() => {
    if (!data) return [];
    const cats = new Set(data.items.map((s) => s.category));
    return Array.from(cats).sort();
  }, [data]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Skills</h1>
        <p className="text-sm text-muted-foreground">Reusable worker skill templates in the registry</p>
      </div>
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search skills..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-8" />
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Category" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <Card>
        <CardContent className="p-0">
          {!data && <div className="px-4 py-6 space-y-2">{[1,2,3,4].map((i) => <div key={i} className="h-12 bg-muted rounded animate-pulse" />)}</div>}
          {data && <SkillTable skills={data.items} total={data.total} />}
        </CardContent>
      </Card>
    </div>
  );
}
```

### Step 1.5: Create SkillDetailPage

- [ ] Create `src/pages/SkillDetailPage.tsx`:

```tsx
import { useParams, useNavigate } from "react-router-dom";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SkillInvocations } from "@/components/skills/SkillInvocations";
import { ArrowLeft, Copy } from "lucide-react";
import { timeAgo } from "@/lib/format";
import type { SkillDetail, SkillInvocationListResponse } from "@/types";

export default function SkillDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: skill } = usePolling<SkillDetail>(() => api.get<SkillDetail>(`/api/skills/${id}`), 5000);
  const { data: invocations } = usePolling<SkillInvocationListResponse>(() => api.get<SkillInvocationListResponse>(`/api/skills/${id}/invocations`), 5000);

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground" onClick={() => navigate("/skills")}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Skills
        </Button>
        {!skill && <div className="space-y-2 animate-pulse"><div className="h-7 w-1/2 bg-muted rounded" /><div className="h-4 w-1/3 bg-muted rounded" /></div>}
        {skill && (
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-foreground">{skill.skill_name}</h1>
              <Badge variant="outline" className="text-[10px]">{skill.category}</Badge>
              <Badge variant="outline" className="text-[10px]">v{skill.version}</Badge>
              <span className={`text-xs ${skill.is_active ? "text-green-400" : "text-muted-foreground"}`}>{skill.is_active ? "Active" : "Inactive"}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">{skill.description}</p>
            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
              <span>Namespace: <span className="font-mono">{skill.namespace}</span></span>
              <span className="text-green-400">{skill.success_count ?? 0} success</span>
              <span className="text-red-400">{skill.failure_count ?? 0} failure</span>
              <span>Last used: {skill.last_used_at ? timeAgo(skill.last_used_at) : "Never"}</span>
            </div>
          </div>
        )}
      </div>

      {/* Stats Row */}
      {skill && (
        <div className="grid grid-cols-3 gap-3">
          <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-2xl font-bold text-green-400">{skill.success_count ?? 0}</p><p className="text-xs text-muted-foreground">Successes</p></CardContent></Card>
          <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-2xl font-bold text-red-400">{skill.failure_count ?? 0}</p><p className="text-xs text-muted-foreground">Failures</p></CardContent></Card>
          <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-2xl font-bold text-foreground">{Math.round(((skill.success_count ?? 0) / Math.max(1, (skill.success_count ?? 0) + (skill.failure_count ?? 0))) * 100)}%</p><p className="text-xs text-muted-foreground">Success Rate</p></CardContent></Card>
        </div>
      )}

      {/* Template */}
      {skill?.agent_template && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Agent Template</CardTitle>
              <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => navigator.clipboard.writeText(skill.agent_template)}><Copy className="h-3 w-3" /></Button>
            </div>
          </CardHeader>
          <CardContent><pre className="text-[11px] font-mono bg-muted/50 p-3 rounded overflow-auto max-h-60">{skill.agent_template}</pre></CardContent>
        </Card>
      )}

      {/* Invocations */}
      <SkillInvocations data={invocations} />
    </div>
  );
}
```

### Step 1.6: Wire into App.tsx

- [ ] Add imports for SkillsPage and SkillDetailPage. Replace placeholder routes for /skills and /skills/:id.

### Step 1.7: Build and verify

- [ ] `cd dashboard && npm run build`

### Step 1.8: Commit

```bash
git add dashboard/src/
git commit -m "feat: add Skills page with search, detail view, and invocation history

Skills list with category filter and search. Detail view shows template,
success/failure stats, and invocation history table.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Sessions Page (List + Detail with Recordings)

**Files:**
- Create: `src/components/sessions/SessionTable.tsx`
- Create: `src/components/sessions/RecordingSteps.tsx`
- Create: `src/pages/SessionsPage.tsx`
- Create: `src/pages/SessionDetailPage.tsx`
- Modify: `src/App.tsx`

### Step 2.1: Create SessionTable component

- [ ] Create `src/components/sessions/SessionTable.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, formatDuration } from "@/lib/format";
import type { SessionSummary } from "@/types";

interface SessionTableProps { sessions: SessionSummary[]; total: number; }

export function SessionTable({ sessions, total }: SessionTableProps) {
  const navigate = useNavigate();
  if (sessions.length === 0) return <p className="text-sm text-muted-foreground text-center py-12">No sessions found</p>;
  return (
    <div>
      <Table>
        <TableHeader><TableRow>
          <TableHead>Task</TableHead>
          <TableHead className="w-24">Agent</TableHead>
          <TableHead className="w-20">Category</TableHead>
          <TableHead className="w-20">Status</TableHead>
          <TableHead className="w-16 text-center">OK</TableHead>
          <TableHead className="w-20">Duration</TableHead>
          <TableHead className="w-24">Started</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {sessions.map((s) => (
            <TableRow key={s.session_id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/sessions/${s.session_id}`)}>
              <TableCell className="text-sm">{s.task_title || s.task_id}</TableCell>
              <TableCell><Badge variant="outline" className="text-[10px] h-4 px-1">{s.agent_name || s.agent_id}</Badge></TableCell>
              <TableCell className="text-xs font-mono text-muted-foreground">{s.browser_category || "—"}</TableCell>
              <TableCell><StatusBadge status={s.status} /></TableCell>
              <TableCell className="text-center">{s.success === 1 ? <span className="text-green-400">✓</span> : s.success === 0 ? <span className="text-red-400">✗</span> : <span className="text-muted-foreground">—</span>}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{formatDuration(s.duration_seconds)}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{timeAgo(s.started_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground mt-2 px-2">Showing {sessions.length} of {total} sessions</p>
    </div>
  );
}
```

### Step 2.2: Create RecordingSteps component

- [ ] Create `src/components/sessions/RecordingSteps.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { SessionRecording } from "@/types";

interface RecordingStepsProps { recordings: SessionRecording[]; }

function actionColor(actionType: string): string {
  switch (actionType) {
    case "navigate": return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "click": return "bg-green-500/15 text-green-400 border-green-500/30";
    case "fill": return "bg-purple-500/15 text-purple-400 border-purple-500/30";
    case "screenshot": return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "wait": return "bg-slate-500/15 text-slate-400 border-slate-500/30";
    case "extract": return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
    case "assert": return "bg-indigo-500/15 text-indigo-400 border-indigo-500/30";
    case "auto_login": return "bg-pink-500/15 text-pink-400 border-pink-500/30";
    default: return "bg-slate-500/15 text-slate-400 border-slate-500/30";
  }
}

export function RecordingSteps({ recordings }: RecordingStepsProps) {
  if (recordings.length === 0) return <p className="text-sm text-muted-foreground text-center py-4">No recordings</p>;
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Step Recordings ({recordings.length})</CardTitle></CardHeader>
      <CardContent>
        <div className="space-y-2">
          {recordings.map((rec, idx) => (
            <div key={rec.recording_id} className="flex items-start gap-3 p-2 rounded bg-muted/30">
              <span className="text-xs font-mono text-muted-foreground w-6 text-right shrink-0">{rec.step_number}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <Badge variant="outline" className={`text-[10px] h-4 px-1 ${actionColor(rec.action_type)}`}>{rec.action_type}</Badge>
                  {rec.duration_ms !== null && <span className="text-[10px] text-muted-foreground">{rec.duration_ms}ms</span>}
                </div>
                {rec.target && <p className="text-xs font-mono text-muted-foreground truncate">{rec.target}</p>}
                {rec.value && <p className="text-xs text-muted-foreground">→ {rec.value}</p>}
                {rec.result && <p className="text-[10px] text-green-400/80 mt-0.5">{rec.result}</p>}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

### Step 2.3: Create SessionsPage

- [ ] Create `src/pages/SessionsPage.tsx`:

```tsx
import { useState, useMemo, useCallback } from "react";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SessionTable } from "@/components/sessions/SessionTable";
import type { SessionListResponse } from "@/types";

export default function SessionsPage() {
  const [statusFilter, setStatusFilter] = useState("all");

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", "50");
    if (statusFilter !== "all") params.set("status", statusFilter);
    return params.toString();
  }, [statusFilter]);

  const fetcher = useCallback(() => api.get<SessionListResponse>(`/api/sessions?${queryString}`), [queryString]);
  const { data } = usePolling<SessionListResponse>(fetcher, 5000);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Sessions</h1>
        <p className="text-sm text-muted-foreground">Agent execution sessions and browser automation recordings</p>
      </div>
      <div className="flex items-center gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="timeout">Timeout</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Card>
        <CardContent className="p-0">
          {!data && <div className="px-4 py-6 space-y-2">{[1,2,3,4].map((i) => <div key={i} className="h-10 bg-muted rounded animate-pulse" />)}</div>}
          {data && <SessionTable sessions={data.items} total={data.total} />}
        </CardContent>
      </Card>
    </div>
  );
}
```

### Step 2.4: Create SessionDetailPage

- [ ] Create `src/pages/SessionDetailPage.tsx`:

```tsx
import { useParams, useNavigate } from "react-router-dom";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { RecordingSteps } from "@/components/sessions/RecordingSteps";
import { ArrowLeft, Copy } from "lucide-react";
import { timeAgo, formatDuration } from "@/lib/format";
import type { SessionDetail } from "@/types";

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: session } = usePolling<SessionDetail>(() => api.get<SessionDetail>(`/api/sessions/${id}`), 5000);

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground" onClick={() => navigate("/sessions")}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Sessions
        </Button>
        {!session && <div className="space-y-2 animate-pulse"><div className="h-7 w-1/2 bg-muted rounded" /><div className="h-4 w-1/3 bg-muted rounded" /></div>}
        {session && (
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{session.task_title || session.session_id.slice(0, 8)}</h1>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <Badge variant="outline" className="text-[10px] h-4 px-1">{session.agent_name || session.agent_id}</Badge>
                {session.browser_category && <span className="font-mono">{session.browser_category}</span>}
                <span>{timeAgo(session.started_at)}</span>
                <span>Duration: {formatDuration(session.duration_seconds)}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={session.status} />
              {session.success === 1 && <Badge className="bg-green-600 text-xs">Success</Badge>}
              {session.success === 0 && <Badge variant="destructive" className="text-xs">Failed</Badge>}
            </div>
          </div>
        )}
      </div>

      {session?.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
          <p className="text-sm font-medium text-red-400">Error</p>
          <p className="text-xs text-red-400/80 mt-1">{session.error_message}</p>
        </div>
      )}

      {session?.summary && (
        <Card><CardContent className="pt-4"><p className="text-sm text-muted-foreground">{session.summary}</p></CardContent></Card>
      )}

      {session && <RecordingSteps recordings={session.recordings || []} />}

      {session?.output_snapshot && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Output Snapshot</CardTitle>
              <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => navigator.clipboard.writeText(session.output_snapshot!)}><Copy className="h-3 w-3" /></Button>
            </div>
          </CardHeader>
          <CardContent><pre className="text-[11px] font-mono bg-muted/50 p-3 rounded overflow-auto max-h-60">{session.output_snapshot}</pre></CardContent>
        </Card>
      )}
    </div>
  );
}
```

### Step 2.5: Wire into App.tsx

- [ ] Add imports. Replace placeholder routes for /sessions and /sessions/:id.

### Step 2.6: Build, verify, commit

```bash
git commit -m "feat: add Sessions page with list, detail view, and step recordings

Session list with status filter. Detail view shows summary, error banner,
step-by-step recording replay with action type badges, and output snapshot.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Improvements Page (Log + Stats)

**Files:**
- Create: `src/pages/ImprovementsPage.tsx`
- Modify: `src/App.tsx`

### Step 3.1: Create ImprovementsPage

- [ ] Create `src/pages/ImprovementsPage.tsx`:

A single page with:
- Stats overview cards (total patterns, avg impact)
- Category breakdown (bar-style display)
- Top improving agents list
- Improvement log table with category badge, agent, summary, impact score, timestamp

Uses usePolling on /api/improvements and /api/improvements/stats.

### Step 3.2: Wire into App.tsx, build, commit

```bash
git commit -m "feat: add Improvements page with stats overview and pattern log

Shows total patterns, average impact, category breakdown, top improving
agents, and full improvement log with category/agent/impact filters.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Settings Page (Config + Credentials + Cron)

**Files:**
- Create: `src/pages/SettingsPage.tsx`
- Modify: `src/App.tsx`

### Step 4.1: Create SettingsPage

- [ ] Create `src/pages/SettingsPage.tsx`:

A tabbed page (using shadcn Tabs or manual tab buttons) with 3 sections:
1. **Configuration** — Table of key-value pairs with inline edit. PUT /api/config/:key on save.
2. **Credentials** — Table of credentials (domain, label, auth_type). Add form + delete buttons. No secrets shown.
3. **Cron Jobs** — Table of cron schedules (agent, expression, enabled, fires, last/next fire). Add form + delete.

### Step 4.2: Install shadcn tabs component

```bash
npx shadcn@latest add tabs -y
```

### Step 4.3: Wire into App.tsx, build, commit

```bash
git commit -m "feat: add Settings page with config editor, credentials, and cron management

Three-tab layout: Configuration (inline edit key-value pairs), Credentials
(add/delete, secrets hidden), Cron Jobs (add/delete schedules).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Final Production Build + Push

### Step 5.1: Production build
```bash
cd dashboard && npm run build
```

### Step 5.2: Commit and push
```bash
git add dashboard/dist/
git commit -m "build: final production bundle with all 9 dashboard pages"
git push
```

---

## Summary

After completing all 5 tasks:
1. **Skills** — Searchable list, detail with template + invocation history
2. **Sessions** — Filtered list, detail with step-by-step recording replay
3. **Improvements** — Stats cards + category breakdown + improvement log
4. **Settings** — Config editor, credentials manager, cron scheduler
5. **Production build** — All 9 pages served from dashboard/dist/

Combined with Plan A (Overview) and Plan B (Requests, Tasks, Agents, Releases), the dashboard is feature-complete.
