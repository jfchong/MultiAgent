import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, formatDuration } from "@/lib/format";
import type { AgentDetail } from "@/types";

interface AgentStatsProps { agent: AgentDetail; }

export function AgentStats({ agent }: AgentStatsProps) {
  const navigate = useNavigate();
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-2xl font-bold text-foreground">{agent.run_count}</p><p className="text-xs text-muted-foreground">Total Runs</p></CardContent></Card>
        <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-2xl font-bold text-red-400">{agent.error_count}</p><p className="text-xs text-muted-foreground">Errors</p></CardContent></Card>
        <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-2xl font-bold text-green-400">{Math.round(agent.success_rate * 100)}%</p><p className="text-xs text-muted-foreground">Success Rate</p></CardContent></Card>
        <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-lg font-bold text-foreground">{agent.last_run_at ? timeAgo(agent.last_run_at) : "Never"}</p><p className="text-xs text-muted-foreground">Last Run</p></CardContent></Card>
      </div>
      {agent.current_task && (
        <Card className="border-blue-500/30">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-blue-400">Current Task</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center justify-between cursor-pointer hover:opacity-80" onClick={() => navigate(`/tasks/${agent.current_task!.task_id}`)}>
              <span className="text-sm font-medium">{agent.current_task.title}</span>
              <StatusBadge status={agent.current_task.status} />
            </div>
          </CardContent>
        </Card>
      )}
      {agent.recent_tasks && agent.recent_tasks.length > 0 && (
        <Card>
          <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Recent Tasks</CardTitle></CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Title</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-20">Duration</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {agent.recent_tasks.map((task) => (
                  <TableRow key={task.task_id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/tasks/${task.task_id}`)}>
                    <TableCell className="text-sm">{task.title}</TableCell>
                    <TableCell><StatusBadge status={task.status} /></TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatDuration(task.duration_seconds)}</TableCell>
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
