import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { KpiCards } from "@/components/overview/KpiCards";
import { TaskPipeline } from "@/components/overview/TaskPipeline";
import { ActivityFeed } from "@/components/overview/ActivityFeed";
import { AgentStatusGrid } from "@/components/overview/AgentStatusGrid";

interface StatusData {
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

interface PipelineData {
  pending: number;
  assigned: number;
  awaiting_release: number;
  in_progress: number;
  blocked: number;
  review: number;
  completed: number;
  failed: number;
  cancelled: number;
}

interface ActivityItem {
  id: string;
  type: string;
  event_type: string;
  agent_id: string | null;
  agent_name: string | null;
  task_id: string | null;
  task_title: string | null;
  summary: string;
  timestamp: string;
  data: Record<string, unknown>;
}

interface Agent {
  agent_id: string;
  agent_name: string;
  agent_type: string;
  level: number;
  status: string;
  run_count: number;
  active_task_count: number;
}

export default function OverviewPage() {
  const { data: status } = usePolling<StatusData>(
    () => api.get<StatusData>("/api/status"),
    5000
  );

  const { data: pipeline } = usePolling<PipelineData>(
    () => api.get<PipelineData>("/api/pipeline"),
    5000
  );

  const { data: activity } = usePolling<ActivityItem[]>(
    () => api.get<ActivityItem[]>("/api/activity?limit=20"),
    5000
  );

  const { data: agents } = usePolling<Agent[]>(
    () => api.get<Agent[]>("/api/agents"),
    5000
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Overview</h1>
        <p className="text-sm text-muted-foreground">Ultra Agent System status at a glance</p>
      </div>

      <KpiCards data={status} />

      <TaskPipeline data={pipeline} />

      <div className="grid grid-cols-5 gap-4">
        <div className="col-span-3">
          <ActivityFeed data={activity} />
        </div>
        <div className="col-span-2">
          <AgentStatusGrid data={agents} />
        </div>
      </div>
    </div>
  );
}
