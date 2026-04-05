import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search } from "lucide-react";

interface TaskFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusChange: (value: string) => void;
  agentFilter: string;
  onAgentChange: (value: string) => void;
  agents: { agent_id: string; agent_name: string }[];
}

const STATUSES = ["all","pending","assigned","in_progress","awaiting_release","blocked","review","completed","failed","cancelled"];

export function TaskFilters({ search, onSearchChange, statusFilter, onStatusChange, agentFilter, onAgentChange, agents }: TaskFiltersProps) {
  return (
    <div className="flex items-center gap-3">
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input placeholder="Search tasks..." value={search} onChange={(e) => onSearchChange(e.target.value)} className="pl-8" />
      </div>
      <Select value={statusFilter} onValueChange={onStatusChange}>
        <SelectTrigger className="w-40"><SelectValue placeholder="Status" /></SelectTrigger>
        <SelectContent>
          {STATUSES.map((s) => (<SelectItem key={s} value={s}>{s === "all" ? "All Statuses" : s.replace(/_/g, " ")}</SelectItem>))}
        </SelectContent>
      </Select>
      <Select value={agentFilter} onValueChange={onAgentChange}>
        <SelectTrigger className="w-40"><SelectValue placeholder="Agent" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Agents</SelectItem>
          {agents.map((a) => (<SelectItem key={a.agent_id} value={a.agent_id}>{a.agent_name}</SelectItem>))}
        </SelectContent>
      </Select>
    </div>
  );
}
