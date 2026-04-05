import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { AutoReleaseRule } from "@/types";

interface AutoReleaseRulesProps { rules: AutoReleaseRule[] | null; onAction: () => void; }

export function AutoReleaseRules({ rules, onAction }: AutoReleaseRulesProps) {
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  async function handleDelete(ruleId: string) {
    await api.delete(`/api/rules/${ruleId}`);
    setDeleteTarget(null);
    onAction();
  }

  return (
    <>
      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Auto-Release Rules{rules ? ` (${rules.length})` : ""}</CardTitle></CardHeader>
        <CardContent className="p-0">
          {!rules && <div className="px-4 pb-4 space-y-2">{[1,2].map((i) => <div key={i} className="h-10 bg-muted rounded animate-pulse" />)}</div>}
          {rules && rules.length === 0 && <p className="text-sm text-muted-foreground text-center py-6">No auto-release rules yet. Click "Auto-Release" on a pending release to create one.</p>}
          {rules && rules.length > 0 && (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Agent Type</TableHead>
                <TableHead>Action Type</TableHead>
                <TableHead>Title Pattern</TableHead>
                <TableHead className="w-16 text-center">Fires</TableHead>
                <TableHead className="w-16">Status</TableHead>
                <TableHead className="w-10" />
              </TableRow></TableHeader>
              <TableBody>
                {rules.map((rule) => (
                  <TableRow key={rule.rule_id}>
                    <TableCell className="text-sm">{rule.match_agent_type || "*"}</TableCell>
                    <TableCell className="text-sm">{rule.match_action_type || "*"}</TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">{rule.match_title_pattern || "—"}</TableCell>
                    <TableCell className="text-center text-sm">{rule.fire_count}</TableCell>
                    <TableCell><span className={`text-xs ${rule.is_enabled ? "text-green-400" : "text-muted-foreground"}`}>{rule.is_enabled ? "Active" : "Disabled"}</span></TableCell>
                    <TableCell><Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-muted-foreground hover:text-red-400" onClick={() => setDeleteTarget(rule.rule_id)}><Trash2 className="h-3 w-3" /></Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      <Dialog open={deleteTarget !== null} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete Rule</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Delete this auto-release rule? Future matching releases will require manual approval.</p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={() => deleteTarget && handleDelete(deleteTarget)}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
