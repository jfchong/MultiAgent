import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo, formatDuration } from "@/lib/format";
import type { SkillInvocationListResponse } from "@/types";

interface SkillInvocationsProps { data: SkillInvocationListResponse | null; }

export function SkillInvocations({ data }: SkillInvocationsProps) {
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Invocation History{data ? ` (${data.total})` : ""}</CardTitle></CardHeader>
      <CardContent className="p-0">
        {!data && <div className="px-4 pb-4 space-y-2">{[1,2,3].map((i) => <div key={i} className="h-10 bg-muted rounded animate-pulse" />)}</div>}
        {data && data.items.length === 0 && <p className="text-sm text-muted-foreground text-center py-6">No invocations yet</p>}
        {data && data.items.length > 0 && (
          <Table>
            <TableHeader><TableRow>
              <TableHead>Agent</TableHead>
              <TableHead className="w-24">Status</TableHead>
              <TableHead className="w-20">Duration</TableHead>
              <TableHead className="w-24">When</TableHead>
              <TableHead>Error</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {data.items.map((inv) => (
                <TableRow key={inv.invocation_id}>
                  <TableCell className="text-sm font-mono">{inv.agent_id}</TableCell>
                  <TableCell><StatusBadge status={inv.status} /></TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatDuration(inv.duration_seconds)}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{timeAgo(inv.created_at)}</TableCell>
                  <TableCell className="text-xs text-red-400 truncate max-w-xs">{inv.error_message || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
