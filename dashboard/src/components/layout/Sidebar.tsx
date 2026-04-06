import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Send,
  ListTodo,
  Bot,
  ShieldCheck,
  Wrench,
  Monitor,
  TrendingUp,
  Settings,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";

interface StatusData {
  pending_releases: number;
}

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Overview" },
  { to: "/requests", icon: Send, label: "Requests" },
  { to: "/tasks", icon: ListTodo, label: "Tasks" },
  { to: "/agents", icon: Bot, label: "Agents" },
  { to: "/releases", icon: ShieldCheck, label: "Releases", badgeKey: "pending_releases" as const },
  { to: "/skills", icon: Wrench, label: "Skills" },
  { to: "/sessions", icon: Monitor, label: "Sessions" },
  { to: "/improvements", icon: TrendingUp, label: "Improvements" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const { data: status } = usePolling<StatusData>(
    () => api.get<StatusData>("/api/status"),
    5000
  );

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-60 border-r border-border bg-card">
      <div className="flex h-14 items-center border-b border-border px-4">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-md bg-primary flex items-center justify-center">
            <span className="text-xs font-bold text-primary-foreground">U</span>
          </div>
          <span className="text-sm font-semibold text-foreground">Ultra Agent</span>
        </div>
      </div>
      <ScrollArea className="h-[calc(100vh-3.5rem)] py-2">
        <nav className="flex flex-col gap-1 px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                }`
              }
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <span className="flex-1">{item.label}</span>
              {item.badgeKey && status && status[item.badgeKey] > 0 && (
                <Badge variant="secondary" className="h-5 min-w-[20px] px-1.5 text-xs">
                  {status[item.badgeKey]}
                </Badge>
              )}
            </NavLink>
          ))}
        </nav>
      </ScrollArea>
    </aside>
  );
}
