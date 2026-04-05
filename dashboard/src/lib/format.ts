export function timeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export function statusColor(status: string): string {
  switch (status) {
    case "completed": case "approved": case "auto_released": return "bg-green-500/15 text-green-400 border-green-500/30";
    case "in_progress": case "running": return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "pending": case "idle": return "bg-slate-500/15 text-slate-400 border-slate-500/30";
    case "assigned": return "bg-indigo-500/15 text-indigo-400 border-indigo-500/30";
    case "awaiting_release": case "review": return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "blocked": return "bg-orange-500/15 text-orange-400 border-orange-500/30";
    case "failed": case "error": case "rejected": return "bg-red-500/15 text-red-400 border-red-500/30";
    case "cancelled": return "bg-gray-500/15 text-gray-500 border-gray-500/30";
    default: return "bg-slate-500/15 text-slate-400 border-slate-500/30";
  }
}

export function statusDot(status: string): string {
  switch (status) {
    case "completed": case "approved": return "bg-green-500";
    case "in_progress": case "running": return "bg-blue-500";
    case "pending": case "idle": return "bg-slate-400";
    case "assigned": return "bg-indigo-500";
    case "awaiting_release": case "review": return "bg-amber-500";
    case "failed": case "error": return "bg-red-500";
    case "blocked": return "bg-orange-500";
    default: return "bg-slate-400";
  }
}

export function priorityColor(priority: number): string {
  if (priority <= 2) return "text-red-400";
  if (priority <= 4) return "text-amber-400";
  if (priority <= 6) return "text-blue-400";
  return "text-slate-400";
}

export function actionTypeColor(actionType: string): string {
  switch (actionType) {
    case "plan": return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "research": return "bg-purple-500/15 text-purple-400 border-purple-500/30";
    case "design": return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
    case "execute": return "bg-green-500/15 text-green-400 border-green-500/30";
    case "review": return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "store": return "bg-indigo-500/15 text-indigo-400 border-indigo-500/30";
    default: return "bg-slate-500/15 text-slate-400 border-slate-500/30";
  }
}
