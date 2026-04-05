import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, priorityColor } from "@/lib/format";
import type { RequestItem } from "@/types";

interface RequestHistoryProps { data: { items: RequestItem[]; total: number } | null; }

export function RequestHistory({ data }: RequestHistoryProps) {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Request History{data ? ` (${data.total})` : ""}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {!data && <div className="px-4 pb-4 space-y-2">{[1,2,3].map((i) => <div key={i} className="h-10 bg-muted rounded animate-pulse" />)}</div>}
        {data && data.items.length === 0 && <p className="text-sm text-muted-foreground text-center py-8 px-4">No requests yet — submit one above!</p>}
        {data && data.items.length > 0 && (
          <Table>
            <TableHeader><TableRow>
              <TableHead>Title</TableHead>
              <TableHead className="w-28">Status</TableHead>
              <TableHead className="w-16 text-center">Priority</TableHead>
              <TableHead className="w-24">Created</TableHead>
              <TableHead className="w-24">Progress</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.items.map((item) => (
                <TableRow key={item.task_id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/tasks/${item.task_id}`)}>
                  <TableCell className="font-medium text-sm">{item.title}</TableCell>
                  <TableCell><StatusBadge status={item.status} /></TableCell>
                  <TableCell className={`text-center font-mono text-sm ${priorityColor(item.priority)}`}>{item.priority}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{timeAgo(item.created_at)}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{item.subtask_count > 0 ? `${item.completed_subtask_count}/${item.subtask_count}` : "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
