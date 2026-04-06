import { useParams, useNavigate } from "react-router-dom";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { RecordingSteps } from "@/components/sessions/RecordingSteps";
import { ArrowLeft, Copy } from "lucide-react";
import { timeAgo, formatDuration } from "@/lib/format";
import type { SessionDetail } from "@/types";

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: session } = usePolling<SessionDetail>(() => api.get<SessionDetail>(`/api/sessions/${id}`), 5000);
  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground" onClick={() => navigate("/sessions")}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Sessions
        </Button>
        {!session && <div className="space-y-2 animate-pulse"><div className="h-7 w-1/2 bg-muted rounded" /><div className="h-4 w-1/3 bg-muted rounded" /></div>}
        {session && (
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{session.task_title || session.session_id.slice(0, 8)}</h1>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <Badge variant="outline" className="text-[10px] h-4 px-1">{session.agent_name || session.agent_id}</Badge>
                {session.browser_category && <span className="font-mono">{session.browser_category}</span>}
                <span>{timeAgo(session.started_at)}</span>
                <span>Duration: {formatDuration(session.duration_seconds)}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={session.status} />
              {session.success === 1 && <Badge className="bg-green-600 text-xs">Success</Badge>}
              {session.success === 0 && <Badge variant="destructive" className="text-xs">Failed</Badge>}
            </div>
          </div>
        )}
      </div>
      {session?.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
          <p className="text-sm font-medium text-red-400">Error</p>
          <p className="text-xs text-red-400/80 mt-1">{session.error_message}</p>
        </div>
      )}
      {session?.summary && <Card><CardContent className="pt-4"><p className="text-sm text-muted-foreground">{session.summary}</p></CardContent></Card>}
      {session && <RecordingSteps recordings={session.recordings || []} />}
      {session?.output_snapshot && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Output Snapshot</CardTitle>
              <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => navigator.clipboard.writeText(session.output_snapshot!)}><Copy className="h-3 w-3" /></Button>
            </div>
          </CardHeader>
          <CardContent><pre className="text-[11px] font-mono bg-muted/50 p-3 rounded overflow-auto max-h-60">{session.output_snapshot}</pre></CardContent>
        </Card>
      )}
    </div>
  );
}
