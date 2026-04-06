import { useNavigate } from "react-router-dom";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, formatDuration, priorityColor } from "@/lib/format";
import type { TaskSummary } from "@/types";

interface TaskTableProps { tasks: TaskSummary[]; total: number; }

export function TaskTable({ tasks, total }: TaskTableProps) {
  const navigate = useNavigate();
  if (tasks.length === 0) return <p className="text-sm text-muted-foreground text-center py-12">No tasks match the current filters</p>;
  return (
    <div>
      <Table>
        <TableHeader><TableRow>
          <TableHead>Title</TableHead>
          <TableHead className="w-28">Status</TableHead>
          <TableHead className="w-28">Agent</TableHead>
          <TableHead className="w-16 text-center">Priority</TableHead>
          <TableHead className="w-24">Created</TableHead>
          <TableHead className="w-20">Duration</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {tasks.map((task) => (
            <TableRow key={task.task_id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/tasks/${task.task_id}`)}>
              <TableCell>
                <div className="flex items-center gap-2">
                  {task.parent_task_id && <span className="text-muted-foreground text-xs">↳</span>}
                  <span className="font-medium text-sm">{task.title}</span>
                </div>
              </TableCell>
              <TableCell><StatusBadge status={task.status} /></TableCell>
              <TableCell>{task.agent_name ? <Badge variant="outline" className="text-[10px] h-5 px-1.5">{task.agent_name}</Badge> : <span className="text-xs text-muted-foreground">—</span>}</TableCell>
              <TableCell className={`text-center font-mono text-sm ${priorityColor(task.priority)}`}>{task.priority}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{timeAgo(task.created_at)}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{formatDuration(task.duration_seconds)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground mt-2 px-2">Showing {tasks.length} of {total} tasks</p>
    </div>
  );
}
