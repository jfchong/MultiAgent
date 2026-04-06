import { useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { timeAgo } from "@/lib/format";
import type { ImprovementListResponse, ImprovementStats } from "@/types";

const CATEGORIES = [
  "success_pattern",
  "failure_pattern",
  "approach_rating",
  "toolkit_feedback",
  "skill_refinement",
  "process_suggestion",
] as const;

const CATEGORY_LABELS: Record<string, string> = {
  success_pattern: "Success Pattern",
  failure_pattern: "Failure Pattern",
  approach_rating: "Approach Rating",
  toolkit_feedback: "Toolkit Feedback",
  skill_refinement: "Skill Refinement",
  process_suggestion: "Process Suggestion",
};

function categoryBadgeClass(category: string): string {
  switch (category) {
    case "success_pattern":
      return "bg-green-500/15 text-green-400 border-green-500/30";
    case "failure_pattern":
      return "bg-red-500/15 text-red-400 border-red-500/30";
    case "approach_rating":
      return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "toolkit_feedback":
      return "bg-purple-500/15 text-purple-400 border-purple-500/30";
    case "skill_refinement":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "process_suggestion":
      return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
    default:
      return "bg-slate-500/15 text-slate-400 border-slate-500/30";
  }
}

function impactScoreClass(score: number | null): string {
  if (score === null) return "text-muted-foreground";
  if (score > 0) return "text-green-400 font-medium";
  if (score < 0) return "text-red-400 font-medium";
  return "text-muted-foreground";
}

function formatImpact(score: number | null): string {
  if (score === null) return "—";
  return score > 0 ? `+${score.toFixed(1)}` : score.toFixed(1);
}

export default function ImprovementsPage() {
  const navigate = useNavigate();
  const [categoryFilter, setCategoryFilter] = useState("all");

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", "50");
    if (categoryFilter !== "all") params.set("category", categoryFilter);
    return params.toString();
  }, [categoryFilter]);

  const fetcher = useCallback(
    () => api.get<ImprovementListResponse>(`/api/improvements?${queryString}`),
    [queryString]
  );

  const { data } = usePolling<ImprovementListResponse>(fetcher, 10000);
  const { data: stats } = usePolling<ImprovementStats>(
    () => api.get<ImprovementStats>("/api/improvements/stats"),
    15000
  );

  const items = data?.items ?? [];

  const maxCategoryCount = useMemo(() => {
    if (!stats) return 1;
    const counts = Object.values(stats.by_category).map((c) => c.count);
    return Math.max(1, ...counts);
  }, [stats]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Improvements</h1>
        <p className="text-sm text-muted-foreground">
          Patterns, ratings, and feedback logged by agents during task execution
        </p>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* KPI: Total Patterns */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Total Patterns
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-foreground">
              {stats ? stats.total_patterns : <span className="h-8 w-16 bg-muted rounded animate-pulse inline-block" />}
            </div>
            <p className="text-xs text-muted-foreground mt-1">across all categories</p>
          </CardContent>
        </Card>

        {/* KPI: Avg Impact Score */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Avg Impact Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className={`text-3xl font-bold ${
                stats
                  ? stats.avg_impact_score > 0
                    ? "text-green-400"
                    : stats.avg_impact_score < 0
                    ? "text-red-400"
                    : "text-foreground"
                  : "text-foreground"
              }`}
            >
              {stats ? (
                stats.avg_impact_score > 0
                  ? `+${stats.avg_impact_score.toFixed(2)}`
                  : stats.avg_impact_score.toFixed(2)
              ) : (
                <span className="h-8 w-16 bg-muted rounded animate-pulse inline-block" />
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-1">average across all logged improvements</p>
          </CardContent>
        </Card>
      </div>

      {/* Category Breakdown + Top Agents */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Category Breakdown */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">By Category</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!stats && (
              <div className="space-y-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-6 bg-muted rounded animate-pulse" />
                ))}
              </div>
            )}
            {stats &&
              CATEGORIES.map((cat) => {
                const entry = stats.by_category[cat];
                if (!entry) return null;
                const barWidth = Math.round((entry.count / maxCategoryCount) * 100);
                return (
                  <div key={cat} className="flex items-center gap-3">
                    <div className="w-36 shrink-0">
                      <Badge
                        variant="outline"
                        className={`text-xs ${categoryBadgeClass(cat)}`}
                      >
                        {CATEGORY_LABELS[cat]}
                      </Badge>
                    </div>
                    <div className="flex-1 flex items-center gap-2">
                      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary/50 rounded-full transition-all"
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                      <span className="text-xs text-foreground font-medium w-6 text-right">
                        {entry.count}
                      </span>
                    </div>
                    <span
                      className={`text-xs w-12 text-right shrink-0 ${
                        entry.avg_impact > 0
                          ? "text-green-400"
                          : entry.avg_impact < 0
                          ? "text-red-400"
                          : "text-muted-foreground"
                      }`}
                    >
                      {entry.avg_impact > 0
                        ? `+${entry.avg_impact.toFixed(1)}`
                        : entry.avg_impact.toFixed(1)}
                    </span>
                  </div>
                );
              })}
            {stats && Object.keys(stats.by_category).length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">No category data yet</p>
            )}
          </CardContent>
        </Card>

        {/* Top Improving Agents */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Top Improving Agents</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {!stats && (
              <div className="px-4 py-4 space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-8 bg-muted rounded animate-pulse" />
                ))}
              </div>
            )}
            {stats && stats.top_improving_agents.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-6">No agent data yet</p>
            )}
            {stats && stats.top_improving_agents.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Agent</TableHead>
                    <TableHead className="w-16 text-right">Count</TableHead>
                    <TableHead className="w-24 text-right">Avg Impact</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {stats.top_improving_agents.map((agent, idx) => (
                    <TableRow key={agent.agent_id ?? idx}>
                      <TableCell className="text-sm">
                        {agent.agent_name ?? agent.agent_id ?? "Unknown"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground text-right">
                        {agent.count}
                      </TableCell>
                      <TableCell
                        className={`text-xs text-right font-medium ${
                          agent.avg_impact > 0
                            ? "text-green-400"
                            : agent.avg_impact < 0
                            ? "text-red-400"
                            : "text-muted-foreground"
                        }`}
                      >
                        {agent.avg_impact > 0
                          ? `+${agent.avg_impact.toFixed(2)}`
                          : agent.avg_impact.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Improvement Log */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-4">
            <CardTitle className="text-sm font-medium">Improvement Log</CardTitle>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-48 h-8 text-xs">
                <SelectValue placeholder="All categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {CATEGORIES.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {CATEGORY_LABELS[cat]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {!data && (
            <div className="px-4 py-4 space-y-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-10 bg-muted rounded animate-pulse" />
              ))}
            </div>
          )}
          {data && items.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No improvement logs found
            </p>
          )}
          {data && items.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-36">Category</TableHead>
                  <TableHead className="w-32">Agent</TableHead>
                  <TableHead>Summary</TableHead>
                  <TableHead className="w-24 text-right">Impact</TableHead>
                  <TableHead className="w-24 text-right">When</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow
                    key={item.log_id}
                    className={
                      item.task_id
                        ? "cursor-pointer hover:bg-muted/50 transition-colors"
                        : undefined
                    }
                    onClick={() => {
                      if (item.task_id) navigate(`/tasks/${item.task_id}`);
                    }}
                  >
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={`text-xs ${categoryBadgeClass(item.category)}`}
                      >
                        {CATEGORY_LABELS[item.category] ?? item.category}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {item.agent_name || item.agent_id ? (
                        <Badge variant="outline" className="text-xs bg-slate-500/10 text-slate-400 border-slate-500/30">
                          {item.agent_name ?? item.agent_id}
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm max-w-xs">
                      <span className="line-clamp-2">{item.summary}</span>
                      {item.task_title && (
                        <span className="block text-xs text-muted-foreground mt-0.5 truncate">
                          {item.task_title}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className={`text-sm text-right tabular-nums ${impactScoreClass(item.impact_score)}`}>
                      {formatImpact(item.impact_score)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground text-right whitespace-nowrap">
                      {timeAgo(item.created_at)}
                    </TableCell>
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
