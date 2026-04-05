import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { timeAgo } from "@/lib/format";
import type { TimelineEvent } from "@/types";

interface TaskTimelineProps { events: TimelineEvent[] | null; }

function eventDotColor(eventType: string): string {
  if (eventType.includes("completed") || eventType.includes("approved")) return "bg-green-500";
  if (eventType.includes("failed") || eventType.includes("rejected") || eventType.includes("error")) return "bg-red-500";
  if (eventType.includes("assigned") || eventType.includes("started") || eventType.includes("in_progress")) return "bg-blue-500";
  if (eventType.includes("release") || eventType.includes("awaiting")) return "bg-amber-500";
  if (eventType.includes("subtask")) return "bg-indigo-500";
  return "bg-slate-500";
}

function eventIcon(eventType: string): string {
  if (eventType.includes("created")) return "●";
  if (eventType.includes("assigned")) return "→";
  if (eventType.includes("started") || eventType.includes("in_progress")) return "▶";
  if (eventType.includes("completed")) return "✓";
  if (eventType.includes("failed")) return "✗";
  if (eventType.includes("release") || eventType.includes("awaiting")) return "⏳";
  if (eventType.includes("subtask")) return "├";
  return "●";
}

function formatEventType(eventType: string): string { return eventType.replace(/_/g, " "); }

function parseEventData(dataJson: string): Record<string, unknown> {
  try { return JSON.parse(dataJson || "{}"); } catch { return {}; }
}

export function TaskTimeline({ events }: TaskTimelineProps) {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Execution Timeline</CardTitle></CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="max-h-[500px] px-4 pb-4">
          {!events && <div className="space-y-3">{[1,2,3].map((i) => <div key={i} className="flex gap-3 animate-pulse"><div className="h-2.5 w-2.5 rounded-full bg-muted mt-1.5" /><div className="flex-1"><div className="h-3 w-2/3 bg-muted rounded mb-1" /><div className="h-2 w-1/3 bg-muted rounded" /></div></div>)}</div>}
          {events && events.length === 0 && <p className="text-sm text-muted-foreground text-center py-4">No events recorded</p>}
          {events && events.length > 0 && (
            <div className="space-y-0">
              {events.map((event, idx) => {
                const data = parseEventData(event.data_json);
                return (
                  <div key={event.event_id} className="flex gap-3 group">
                    <div className="flex flex-col items-center pt-1.5">
                      <div className={`h-2.5 w-2.5 rounded-full shrink-0 ${eventDotColor(event.event_type)}`} />
                      {idx < events.length - 1 && <div className="w-px flex-1 bg-border mt-1" />}
                    </div>
                    <div className="flex-1 pb-4">
                      <div className="flex items-center gap-2 mb-0.5">
                        {event.agent_name && (
                          <Badge variant="outline" className="text-[10px] h-4 px-1 cursor-pointer hover:bg-muted"
                            onClick={(e) => { e.stopPropagation(); navigate(`/agents/${event.agent_id}`); }}>
                            {event.agent_name}
                          </Badge>
                        )}
                        <span className="text-[10px] text-muted-foreground">{timeAgo(event.created_at)}</span>
                      </div>
                      <p className="text-xs text-foreground capitalize">{eventIcon(event.event_type)} {formatEventType(event.event_type)}</p>
                      {Object.keys(data).length > 0 && (
                        <div className="mt-1 p-2 bg-muted/50 rounded text-[10px] font-mono text-muted-foreground">
                          {Object.entries(data).map(([key, val]) => (
                            <div key={key}><span className="text-muted-foreground/70">{key}:</span> {typeof val === "string" ? val : JSON.stringify(val)}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
