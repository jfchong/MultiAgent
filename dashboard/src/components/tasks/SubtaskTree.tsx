import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { SubtaskNode } from "@/types";

interface SubtaskTreeProps { subtasks: SubtaskNode[] | null; }

function statusIcon(status: string): string {
  switch (status) {
    case "completed": return "✅"; case "in_progress": return "⏳"; case "pending": return "○";
    case "failed": return "❌"; case "blocked": return "⏸"; case "awaiting_release": return "🔒";
    case "cancelled": return "—"; default: return "○";
  }
}

function TreeNode({ node, depth }: { node: SubtaskNode; depth: number }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children && node.children.length > 0;
  return (
    <div>
      <div className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-muted/50 cursor-pointer group"
        style={{ paddingLeft: `${depth * 20 + 8}px` }} onClick={() => navigate(`/tasks/${node.task_id}`)}>
        {hasChildren ? (
          <button className="h-4 w-4 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}>
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        ) : <span className="w-4 shrink-0" />}
        <span className="text-sm shrink-0">{statusIcon(node.status)}</span>
        <span className="text-sm text-foreground group-hover:text-primary transition-colors truncate flex-1">{node.title}</span>
        <StatusBadge status={node.status} />
        {node.agent_name && <Badge variant="outline" className="text-[10px] h-4 px-1 shrink-0">{node.agent_name}</Badge>}
      </div>
      {hasChildren && expanded && <div>{node.children.map((child) => <TreeNode key={child.task_id} node={child} depth={depth + 1} />)}</div>}
    </div>
  );
}

export function SubtaskTree({ subtasks }: SubtaskTreeProps) {
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Subtask Tree</CardTitle></CardHeader>
      <CardContent className="p-0 pb-2">
        {!subtasks && <div className="px-4 pb-2 space-y-2">{[1,2,3].map((i) => <div key={i} className="h-8 bg-muted rounded animate-pulse" />)}</div>}
        {subtasks && subtasks.length === 0 && <p className="text-sm text-muted-foreground text-center py-4">No subtasks</p>}
        {subtasks && subtasks.length > 0 && <div>{subtasks.map((node) => <TreeNode key={node.task_id} node={node} depth={0} />)}</div>}
      </CardContent>
    </Card>
  );
}
