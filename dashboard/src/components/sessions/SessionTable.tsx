import { useNavigate } from "react-router-dom";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, formatDuration } from "@/lib/format";
import type { SessionSummary } from "@/types";

interface SessionTableProps { sessions: SessionSummary[]; total: number; }

export function SessionTable({ sessions, total }: SessionTableProps) {
  const navigate = useNavigate();
  if (sessions.length === 0) return <p className="text-sm text-muted-foreground text-center py-12">No sessions found</p>;
  return (
    <div>
      <Table>
        <TableHeader><TableRow>
          <TableHead>Task</TableHead>
          <TableHead className="w-24">Agent</TableHead>
          <TableHead className="w-20">Category</TableHead>
          <TableHead className="w-20">Status</TableHead>
          <TableHead className="w-16 text-center">OK</TableHead>
          <TableHead className="w-20">Duration</TableHead>
          <TableHead className="w-24">Started</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {sessions.map((s) => (
            <TableRow key={s.session_id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/sessions/${s.session_id}`)}>
              <TableCell className="text-sm">{s.task_title || s.task_id}</TableCell>
              <TableCell><Badge variant="outline" className="text-[10px] h-4 px-1">{s.agent_name || s.agent_id}</Badge></TableCell>
              <TableCell className="text-xs font-mono text-muted-foreground">{s.browser_category || "—"}</TableCell>
              <TableCell><StatusBadge status={s.status} /></TableCell>
              <TableCell className="text-center">{s.success === 1 ? <span className="text-green-400">✓</span> : s.success === 0 ? <span className="text-red-400">✗</span> : <span className="text-muted-foreground">—</span>}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{formatDuration(s.duration_seconds)}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{timeAgo(s.started_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground mt-2 px-2">Showing {sessions.length} of {total} sessions</p>
    </div>
  );
}
