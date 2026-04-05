import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ActivityItem {
  id: string;
  type: string;
  event_type: string;
  agent_id: string | null;
  agent_name: string | null;
  task_id: string | null;
  task_title: string | null;
  summary: string;
  timestamp: string;
}

interface ActivityFeedProps {
  data: ActivityItem[] | null;
}

function timeAgo(timestamp: string): string {
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

function eventColor(eventType: string): string {
  if (eventType.includes("completed") || eventType.includes("approved")) return "bg-green-500";
  if (eventType.includes("failed") || eventType.includes("rejected")) return "bg-red-500";
  if (eventType.includes("assigned") || eventType.includes("started")) return "bg-blue-500";
  if (eventType.includes("release") || eventType.includes("awaiting")) return "bg-amber-500";
  if (eventType.includes("request") || eventType.includes("user")) return "bg-purple-500";
  return "bg-slate-500";
}

export function ActivityFeed({ data }: ActivityFeedProps) {
  const navigate = useNavigate();

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[320px] px-4 pb-4">
          {!data && (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex gap-3 animate-pulse">
                  <div className="h-2 w-2 rounded-full bg-muted mt-2" />
                  <div className="flex-1">
                    <div className="h-3 w-3/4 bg-muted rounded mb-1" />
                    <div className="h-2 w-1/4 bg-muted rounded" />
                  </div>
                </div>
              ))}
            </div>
          )}
          {data && data.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">No activity yet</p>
          )}
          {data && data.length > 0 && (
            <div className="space-y-3">
              {data.slice(0, 20).map((item) => (
                <div
                  key={item.id}
                  className="flex gap-3 cursor-pointer group"
                  onClick={() => item.task_id && navigate(`/tasks/${item.task_id}`)}
                >
                  <div className="flex flex-col items-center mt-1.5">
                    <div className={`h-2 w-2 rounded-full ${eventColor(item.event_type)}`} />
                    <div className="w-px flex-1 bg-border mt-1" />
                  </div>
                  <div className="flex-1 pb-3">
                    <div className="flex items-center gap-2 mb-0.5">
                      {item.agent_name && (
                        <Badge variant="outline" className="text-[10px] h-4 px-1">
                          {item.agent_name}
                        </Badge>
                      )}
                      <span className="text-[10px] text-muted-foreground">
                        {timeAgo(item.timestamp)}
                      </span>
                    </div>
                    <p className="text-xs text-foreground group-hover:text-primary transition-colors">
                      {item.summary}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
