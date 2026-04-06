import { useParams, useNavigate } from "react-router-dom";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SkillInvocations } from "@/components/skills/SkillInvocations";
import { ArrowLeft, Copy } from "lucide-react";
import { timeAgo } from "@/lib/format";
import type { SkillDetail, SkillInvocationListResponse } from "@/types";

export default function SkillDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: skill } = usePolling<SkillDetail>(() => api.get<SkillDetail>(`/api/skills/${id}`), 5000);
  const { data: invocations } = usePolling<SkillInvocationListResponse>(() => api.get<SkillInvocationListResponse>(`/api/skills/${id}/invocations`), 5000);

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" className="mb-2 -ml-2 text-muted-foreground" onClick={() => navigate("/skills")}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Skills
        </Button>
        {!skill && <div className="space-y-2 animate-pulse"><div className="h-7 w-1/2 bg-muted rounded" /><div className="h-4 w-1/3 bg-muted rounded" /></div>}
        {skill && (
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-foreground">{skill.skill_name}</h1>
              <Badge variant="outline" className="text-[10px]">{skill.category}</Badge>
              <Badge variant="outline" className="text-[10px]">v{skill.version}</Badge>
              <span className={`text-xs ${skill.is_active ? "text-green-400" : "text-muted-foreground"}`}>{skill.is_active ? "Active" : "Inactive"}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">{skill.description}</p>
            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
              <span>Namespace: <span className="font-mono">{skill.namespace}</span></span>
              <span className="text-green-400">{skill.success_count ?? 0} success</span>
              <span className="text-red-400">{skill.failure_count ?? 0} failure</span>
              <span>Last used: {skill.last_used_at ? timeAgo(skill.last_used_at) : "Never"}</span>
            </div>
          </div>
        )}
      </div>

      {/* Stats Row */}
      {skill && (
        <div className="grid grid-cols-3 gap-3">
          <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-2xl font-bold text-green-400">{skill.success_count ?? 0}</p><p className="text-xs text-muted-foreground">Successes</p></CardContent></Card>
          <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-2xl font-bold text-red-400">{skill.failure_count ?? 0}</p><p className="text-xs text-muted-foreground">Failures</p></CardContent></Card>
          <Card><CardContent className="pt-4 pb-3 text-center"><p className="text-2xl font-bold text-foreground">{Math.round(((skill.success_count ?? 0) / Math.max(1, (skill.success_count ?? 0) + (skill.failure_count ?? 0))) * 100)}%</p><p className="text-xs text-muted-foreground">Success Rate</p></CardContent></Card>
        </div>
      )}

      {/* Template */}
      {skill?.agent_template && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Agent Template</CardTitle>
              <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => navigator.clipboard.writeText(skill.agent_template)}><Copy className="h-3 w-3" /></Button>
            </div>
          </CardHeader>
          <CardContent><pre className="text-[11px] font-mono bg-muted/50 p-3 rounded overflow-auto max-h-60">{skill.agent_template}</pre></CardContent>
        </Card>
      )}

      {/* Invocations */}
      <SkillInvocations data={invocations} />
    </div>
  );
}
