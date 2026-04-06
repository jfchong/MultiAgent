import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Agent {
  agent_id: string;
  agent_name: string;
  agent_type: string;
  level: number;
  status: string;
  run_count: number;
  active_task_count: number;
}

interface AgentStatusGridProps {
  data: Agent[] | null;
}

function statusDot(status: string): string {
  switch (status) {
    case "running":
      return "bg-blue-500";
    case "error":
      return "bg-red-500";
    case "idle":
    default:
      return "bg-green-500";
  }
}

export function AgentStatusGrid({ data }: AgentStatusGridProps) {
  const navigate = useNavigate();

  const coreAgents = data?.filter((a) => a.level <= 1) ?? null;

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Agent Status</CardTitle>
      </CardHeader>
      <CardContent>
        {!coreAgents && (
          <div className="grid grid-cols-2 gap-2">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-16 bg-muted rounded animate-pulse" />
            ))}
          </div>
        )}
        {coreAgents && (
          <div className="grid grid-cols-2 gap-2">
            {coreAgents.map((agent) => (
              <div
                key={agent.agent_id}
                className="flex items-center gap-3 rounded-md border border-border p-3 cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => navigate(`/agents/${agent.agent_id}`)}
              >
                <div className={`h-2.5 w-2.5 rounded-full ${statusDot(agent.status)} shrink-0`} />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {agent.agent_name}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {agent.status} &middot; {agent.run_count} runs
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
