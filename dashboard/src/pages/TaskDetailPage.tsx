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
  try { formatted = JSON.stringify(JSON.parse(data), null, 2); } catch { formatted = data; }
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => navigator.clipboard.writeText(formatted)}><Copy className="h-3 w-3" /></Button>
        </div>
      </CardHeader>
      <CardContent>
        <pre className="text-[11px] font-mono bg-muted/50 p-3 rounded overflow-auto max-h-60">{formatted}</pre>
      </CardContent>
    </Card>
  );
}

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: task } = usePolling<TaskDetail>(() => api.get<TaskDetail>(`/api/tasks/${id}`), 5000);
  const { data: timeline } = usePolling<TimelineEvent[]>(() => api.get<TimelineEvent[]>(`/api/tasks/${id}/timeline`), 5000);
  const { data: subtasks } = usePolling<SubtaskNode[]>(() => api.get<SubtaskNode[]>(`/api/tasks/${id}/subtasks`), 5000);

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground" onClick={() => navigate("/tasks")}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Tasks
        </Button>
        {!task && <div className="space-y-2 animate-pulse"><div className="h-7 w-2/3 bg-muted rounded" /><div className="h-4 w-1/3 bg-muted rounded" /></div>}
        {task && (
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{task.title}</h1>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span className="font-mono">{task.task_id.slice(0, 8)}</span>
                <span className={`font-mono ${priorityColor(task.priority)}`}>P{task.priority}</span>
                <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {timeAgo(task.created_at)}</span>
                {task.duration_seconds !== null && <span>Duration: {formatDuration(task.duration_seconds)}</span>}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={task.status} />
              {task.agent_name && <Badge variant="outline" className="cursor-pointer hover:bg-muted" onClick={() => navigate(`/agents/${task.assigned_agent}`)}>{task.agent_name}</Badge>}
            </div>
          </div>
        )}
      </div>
      {task?.status === "failed" && task.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
          <p className="text-sm font-medium text-red-400">Error</p>
          <p className="text-xs text-red-400/80 mt-1">{task.error_message}</p>
        </div>
      )}
      {task?.description && <Card><CardContent className="pt-4"><p className="text-sm text-muted-foreground">{task.description}</p></CardContent></Card>}
      <div className="grid grid-cols-5 gap-4">
        <div className="col-span-3"><TaskTimeline events={timeline} /></div>
        <div className="col-span-2"><SubtaskTree subtasks={subtasks} /></div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <JsonPanel title="Input Data" data={task?.input_data ?? null} />
        <JsonPanel title="Output Data" data={task?.output_data ?? null} />
      </div>
    </div>
  );
}
