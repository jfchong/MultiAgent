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
      <Card><CardContent className="p-0">
        {!data && <div className="px-4 py-6 space-y-2">{[1,2,3,4].map((i) => <div key={i} className="h-10 bg-muted rounded animate-pulse" />)}</div>}
        {data && <SessionTable sessions={data.items} total={data.total} />}
      </CardContent></Card>
    </div>
  );
}
