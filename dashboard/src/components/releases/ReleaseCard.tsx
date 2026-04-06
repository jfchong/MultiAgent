import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Check, X, Zap, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { timeAgo, actionTypeColor } from "@/lib/format";
import type { ReleaseItem } from "@/types";

interface ReleaseCardProps { release: ReleaseItem; onAction: () => void; }

export function ReleaseCard({ release, onAction }: ReleaseCardProps) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<string | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  async function handleApprove() {
    setLoading("approve");
    try { await api.post(`/api/releases/${release.release_id}/approve`); onAction(); } finally { setLoading(null); }
  }
  async function handleReject() {
    setLoading("reject");
    try { await api.post(`/api/releases/${release.release_id}/reject`, { reason: rejectReason || undefined }); setRejectOpen(false); setRejectReason(""); onAction(); } finally { setLoading(null); }
  }
  async function handleAutoRelease() {
    setLoading("auto");
    try { await api.post(`/api/releases/${release.release_id}/auto-release`); onAction(); } finally { setLoading(null); }
  }

  return (
    <>
      <Card className="border-amber-500/20">
        <CardContent className="pt-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-medium text-foreground truncate">{release.title}</h3>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className="text-[10px] h-4 px-1">{release.agent_name || release.agent_id} (L{release.agent_level})</Badge>
                <Badge variant="outline" className={`text-[10px] h-4 px-1 ${actionTypeColor(release.action_type)}`}>{release.action_type}</Badge>
                <span className="text-[10px] text-muted-foreground">{timeAgo(release.created_at)}</span>
              </div>
            </div>
          </div>
          {release.description && <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{release.description}</p>}
          {release.input_preview && <pre className="text-[10px] font-mono bg-muted/50 p-2 rounded mb-3 overflow-hidden max-h-20 text-muted-foreground">{release.input_preview}</pre>}
          <div className="flex items-center gap-2">
            <Button size="sm" className="h-7 text-xs bg-green-600 hover:bg-green-700" onClick={handleApprove} disabled={loading !== null}>
              {loading === "approve" ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Check className="h-3 w-3 mr-1" />} Approve
            </Button>
            <Button size="sm" variant="destructive" className="h-7 text-xs" onClick={() => setRejectOpen(true)} disabled={loading !== null}>
              <X className="h-3 w-3 mr-1" /> Reject
            </Button>
            <Button size="sm" variant="outline" className="h-7 text-xs border-purple-500/30 text-purple-400 hover:bg-purple-500/10" onClick={handleAutoRelease} disabled={loading !== null}>
              {loading === "auto" ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Zap className="h-3 w-3 mr-1" />} Auto-Release
            </Button>
            <Button size="sm" variant="ghost" className="h-7 text-xs ml-auto text-muted-foreground" onClick={() => navigate(`/tasks/${release.task_id}`)}>View Task →</Button>
          </div>
        </CardContent>
      </Card>
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Reject Release</DialogTitle></DialogHeader>
          <Textarea placeholder="Reason for rejection (optional)" value={rejectReason} onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setRejectReason(e.target.value)} rows={3} />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRejectOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleReject} disabled={loading === "reject"}>
              {loading === "reject" ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null} Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
