import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { ReleaseQueue } from "@/components/releases/ReleaseQueue";
import { AutoReleaseRules } from "@/components/releases/AutoReleaseRules";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { timeAgo } from "@/lib/format";
import type { ReleaseListResponse, AutoReleaseRule } from "@/types";

export default function ReleasesPage() {
  const { data: pendingData, refresh: refreshPending } = usePolling<ReleaseListResponse>(() => api.get<ReleaseListResponse>("/api/releases?status=pending"), 5000);
  const { data: recentData, refresh: refreshRecent } = usePolling<ReleaseListResponse>(() => api.get<ReleaseListResponse>("/api/releases?limit=20"), 5000);
  const { data: rules, refresh: refreshRules } = usePolling<AutoReleaseRule[]>(() => api.get<AutoReleaseRule[]>("/api/rules"), 10000);

  function handleAction() { refreshPending(); refreshRecent(); refreshRules(); }

  const recentReviewed = (recentData?.items || []).filter((r) => r.status !== "pending");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Work Releases</h1>
        <p className="text-sm text-muted-foreground">Review and approve agent work before execution</p>
      </div>
      <ReleaseQueue releases={pendingData?.items || []} onAction={handleAction} />
      <AutoReleaseRules rules={rules} onAction={handleAction} />
      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Recent History</CardTitle></CardHeader>
        <CardContent className="p-0">
          {recentReviewed.length === 0 && <p className="text-sm text-muted-foreground text-center py-6">No reviewed releases yet</p>}
          {recentReviewed.length > 0 && (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Title</TableHead>
                <TableHead className="w-24">Agent</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-24">Reviewed</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {recentReviewed.map((release) => (
                  <TableRow key={release.release_id}>
                    <TableCell className="text-sm">{release.title}</TableCell>
                    <TableCell className="text-xs">{release.agent_name || release.agent_id}</TableCell>
                    <TableCell><StatusBadge status={release.status} /></TableCell>
                    <TableCell className="text-xs text-muted-foreground">{release.reviewed_at ? timeAgo(release.reviewed_at) : "—"}</TableCell>
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
