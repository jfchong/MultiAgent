import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ReleaseCard } from "./ReleaseCard";
import { CheckCheck, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { ReleaseItem } from "@/types";

interface ReleaseQueueProps { releases: ReleaseItem[]; onAction: () => void; }

export function ReleaseQueue({ releases, onAction }: ReleaseQueueProps) {
  const [approvingAll, setApprovingAll] = useState(false);
  const pending = releases.filter((r) => r.status === "pending");

  async function handleApproveAll() {
    setApprovingAll(true);
    try { for (const release of pending) { await api.post(`/api/releases/${release.release_id}/approve`); } onAction(); } finally { setApprovingAll(false); }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Pending Releases ({pending.length})</CardTitle>
          {pending.length > 1 && (
            <Button size="sm" className="h-7 text-xs bg-green-600 hover:bg-green-700" onClick={handleApproveAll} disabled={approvingAll}>
              {approvingAll ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <CheckCheck className="h-3 w-3 mr-1" />} Approve All ({pending.length})
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {pending.length === 0 && <div className="text-center py-8"><div className="text-3xl mb-2">✓</div><p className="text-sm text-muted-foreground">No pending releases — all clear!</p></div>}
        {pending.length > 0 && <div className="space-y-3">{pending.map((release) => <ReleaseCard key={release.release_id} release={release} onAction={onAction} />)}</div>}
      </CardContent>
    </Card>
  );
}
