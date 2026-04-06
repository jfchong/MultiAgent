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
  const { data: agent } = usePolling<AgentDetail>(() => api.get<AgentDetail>(`/api/agents/${id}`), 5000);
  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground" onClick={() => navigate("/agents")}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Agents
        </Button>
        {!agent && <div className="space-y-2 animate-pulse"><div className="h-7 w-1/2 bg-muted rounded" /><div className="h-4 w-1/4 bg-muted rounded" /></div>}
        {agent && (
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className={`h-3 w-3 rounded-full ${statusDot(agent.status)}`} />
                  {agent.status === "running" && <div className={`absolute inset-0 h-3 w-3 rounded-full ${statusDot(agent.status)} animate-ping opacity-50`} />}
                </div>
                <h1 className="text-2xl font-bold text-foreground">{agent.agent_name}</h1>
              </div>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span className="capitalize">{agent.agent_type}</span>
                <Badge variant="outline" className="text-[10px] h-4 px-1">L{agent.level}</Badge>
                {agent.parent_agent_id && <span className="cursor-pointer hover:text-primary" onClick={() => navigate(`/agents/${agent.parent_agent_id}`)}>Parent: {agent.parent_agent_id}</span>}
                {agent.last_run_at && <span>Last active: {timeAgo(agent.last_run_at)}</span>}
              </div>
            </div>
            <Badge variant="outline" className={`capitalize ${agent.status === "running" ? "border-blue-500/30 text-blue-400" : agent.status === "error" ? "border-red-500/30 text-red-400" : ""}`}>{agent.status}</Badge>
          </div>
        )}
      </div>
      {agent && <AgentStats agent={agent} />}
    </div>
  );
}
