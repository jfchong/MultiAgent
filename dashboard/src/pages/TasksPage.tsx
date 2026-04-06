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

  const fetcher = useCallback(() => api.get<TaskListResponse>(`/api/tasks?${queryString}`), [queryString]);
  const { data } = usePolling<TaskListResponse>(fetcher, 5000);
  const { data: agents } = usePolling<AgentSummary[]>(() => api.get<AgentSummary[]>("/api/agents"), 30000);
  const agentOptions = useMemo(() => (agents || []).map((a) => ({ agent_id: a.agent_id, agent_name: a.agent_name })), [agents]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Tasks</h1>
        <p className="text-sm text-muted-foreground">Browse and inspect all tasks in the system</p>
      </div>
      <TaskFilters search={search} onSearchChange={setSearch} statusFilter={statusFilter} onStatusChange={setStatusFilter} agentFilter={agentFilter} onAgentChange={setAgentFilter} agents={agentOptions} />
      <Card>
        <CardContent className="p-0">
          {!data && <div className="px-4 py-6 space-y-2">{[1,2,3,4,5].map((i) => <div key={i} className="h-10 bg-muted rounded animate-pulse" />)}</div>}
          {data && <TaskTable tasks={data.items} total={data.total} />}
        </CardContent>
      </Card>
    </div>
  );
}
