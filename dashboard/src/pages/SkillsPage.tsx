import { useState, useMemo, useCallback } from "react";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SkillTable } from "@/components/skills/SkillTable";
import { Search } from "lucide-react";
import type { SkillListResponse } from "@/types";

export default function SkillsPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", "100");
    if (search.trim()) params.set("search", search.trim());
    if (category !== "all") params.set("category", category);
    return params.toString();
  }, [search, category]);

  const fetcher = useCallback(() => api.get<SkillListResponse>(`/api/skills?${queryString}`), [queryString]);
  const { data } = usePolling<SkillListResponse>(fetcher, 5000);

  const categories = useMemo(() => {
    if (!data) return [];
    const cats = new Set(data.items.map((s) => s.category));
    return Array.from(cats).sort();
  }, [data]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Skills</h1>
        <p className="text-sm text-muted-foreground">Reusable worker skill templates in the registry</p>
      </div>
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search skills..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-8" />
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Category" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <Card>
        <CardContent className="p-0">
          {!data && <div className="px-4 py-6 space-y-2">{[1,2,3,4].map((i) => <div key={i} className="h-12 bg-muted rounded animate-pulse" />)}</div>}
          {data && <SkillTable skills={data.items} total={data.total} />}
        </CardContent>
      </Card>
    </div>
  );
}
