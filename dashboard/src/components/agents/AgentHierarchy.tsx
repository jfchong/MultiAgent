import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { statusDot } from "@/lib/format";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { AgentHierarchyNode } from "@/types";

interface AgentHierarchyProps { data: AgentHierarchyNode | null; }

function HierarchyNode({ node, depth }: { node: AgentHierarchyNode; depth: number }) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children && node.children.length > 0;
  return (
    <div>
      <div className="flex items-center gap-2.5 py-2 px-3 rounded-md hover:bg-muted/50 cursor-pointer group transition-colors"
        style={{ paddingLeft: `${depth * 24 + 12}px` }} onClick={() => navigate(`/agents/${node.agent_id}`)}>
        {hasChildren ? (
          <button className="h-4 w-4 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}>
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        ) : <span className="w-4 shrink-0" />}
        <div className="relative shrink-0">
          <div className={`h-2.5 w-2.5 rounded-full ${statusDot(node.status)}`} />
          {node.status === "running" && <div className={`absolute inset-0 h-2.5 w-2.5 rounded-full ${statusDot(node.status)} animate-ping opacity-50`} />}
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">{node.agent_name}</span>
          <span className="text-[10px] text-muted-foreground ml-2">{node.agent_type}</span>
        </div>
        <Badge variant="outline" className="text-[10px] h-4 px-1 shrink-0">L{node.level}</Badge>
        <span className="text-[10px] text-muted-foreground shrink-0">
          {node.run_count} runs{node.error_count > 0 && <span className="text-red-400 ml-1">/ {node.error_count} err</span>}
        </span>
      </div>
      {hasChildren && expanded && <div>{node.children.map((child) => <HierarchyNode key={child.agent_id} node={child} depth={depth + 1} />)}</div>}
    </div>
  );
}

export function AgentHierarchy({ data }: AgentHierarchyProps) {
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Agent Hierarchy</CardTitle></CardHeader>
      <CardContent className="p-0 pb-2">
        {!data && <div className="px-4 pb-2 space-y-2">{[1,2,3,4,5,6,7].map((i) => <div key={i} className="h-9 bg-muted rounded animate-pulse" style={{ marginLeft: `${(i % 3) * 24}px` }} />)}</div>}
        {data && <HierarchyNode node={data} depth={0} />}
      </CardContent>
    </Card>
  );
}
