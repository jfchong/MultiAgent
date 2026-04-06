import { useNavigate } from "react-router-dom";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { timeAgo } from "@/lib/format";
import type { SkillSummary } from "@/types";

interface SkillTableProps { skills: SkillSummary[]; total: number; }

export function SkillTable({ skills, total }: SkillTableProps) {
  const navigate = useNavigate();
  if (skills.length === 0) return <p className="text-sm text-muted-foreground text-center py-12">No skills found</p>;
  return (
    <div>
      <Table>
        <TableHeader><TableRow>
          <TableHead>Name</TableHead>
          <TableHead className="w-24">Category</TableHead>
          <TableHead className="w-20">Version</TableHead>
          <TableHead className="w-20 text-center">Success</TableHead>
          <TableHead className="w-20 text-center">Failure</TableHead>
          <TableHead className="w-20 text-center">Rate</TableHead>
          <TableHead className="w-20">Status</TableHead>
          <TableHead className="w-24">Last Used</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {skills.map((skill) => (
            <TableRow key={skill.skill_id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/skills/${skill.skill_id}`)}>
              <TableCell>
                <div>
                  <span className="font-medium text-sm">{skill.skill_name}</span>
                  <p className="text-[10px] text-muted-foreground truncate max-w-xs">{skill.description}</p>
                </div>
              </TableCell>
              <TableCell><Badge variant="outline" className="text-[10px] h-4 px-1">{skill.category}</Badge></TableCell>
              <TableCell className="text-sm text-center">v{skill.version}</TableCell>
              <TableCell className="text-center text-sm text-green-400">{skill.success_count ?? 0}</TableCell>
              <TableCell className="text-center text-sm text-red-400">{skill.failure_count ?? 0}</TableCell>
              <TableCell className="text-center text-sm">{Math.round(skill.success_rate * 100)}%</TableCell>
              <TableCell>
                <span className={`text-xs ${skill.is_active ? "text-green-400" : "text-muted-foreground"}`}>
                  {skill.is_active ? "Active" : "Inactive"}
                </span>
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">{skill.last_used_at ? timeAgo(skill.last_used_at) : "Never"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground mt-2 px-2">Showing {skills.length} of {total} skills</p>
    </div>
  );
}
