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
  const { data: hierarchy } = usePolling<AgentHierarchyNode>(() => api.get<AgentHierarchyNode>("/api/agents/hierarchy"), 5000);
  const { data: agents } = usePolling<AgentSummary[]>(() => api.get<AgentSummary[]>("/api/agents"), 5000);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Agents</h1>
        <p className="text-sm text-muted-foreground">4-level agent hierarchy — Director → Agents → Sub-Agents → Workers</p>
      </div>
      <AgentHierarchy data={hierarchy} />
      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">All Agents</CardTitle></CardHeader>
        <CardContent className="p-0">
          {!agents && <div className="px-4 pb-4 space-y-2">{[1,2,3,4].map((i) => <div key={i} className="h-10 bg-muted rounded animate-pulse" />)}</div>}
          {agents && (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Agent</TableHead>
                <TableHead className="w-16">Level</TableHead>
                <TableHead className="w-20">Status</TableHead>
                <TableHead className="w-20 text-center">Runs</TableHead>
                <TableHead className="w-20 text-center">Errors</TableHead>
                <TableHead className="w-24 text-center">Success</TableHead>
                <TableHead className="w-24">Last Run</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {agents.map((agent) => (
                  <TableRow key={agent.agent_id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/agents/${agent.agent_id}`)}>
                    <TableCell><div className="flex items-center gap-2"><div className={`h-2 w-2 rounded-full ${statusDot(agent.status)}`} /><span className="font-medium text-sm">{agent.agent_name}</span><span className="text-[10px] text-muted-foreground">{agent.agent_type}</span></div></TableCell>
                    <TableCell><Badge variant="outline" className="text-[10px] h-4 px-1">L{agent.level}</Badge></TableCell>
                    <TableCell className="capitalize text-xs">{agent.status}</TableCell>
                    <TableCell className="text-center text-sm">{agent.run_count}</TableCell>
                    <TableCell className="text-center text-sm"><span className={agent.error_count > 0 ? "text-red-400" : "text-muted-foreground"}>{agent.error_count}</span></TableCell>
                    <TableCell className="text-center text-sm">{Math.round(agent.success_rate * 100)}%</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{agent.last_run_at ? timeAgo(agent.last_run_at) : "—"}</TableCell>
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
