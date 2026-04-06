import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { SessionRecording } from "@/types";

interface RecordingStepsProps { recordings: SessionRecording[]; }

function actionColor(actionType: string): string {
  switch (actionType) {
    case "navigate": return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "click": return "bg-green-500/15 text-green-400 border-green-500/30";
    case "fill": return "bg-purple-500/15 text-purple-400 border-purple-500/30";
    case "screenshot": return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "wait": return "bg-slate-500/15 text-slate-400 border-slate-500/30";
    case "extract": return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
    case "assert": return "bg-indigo-500/15 text-indigo-400 border-indigo-500/30";
    case "auto_login": return "bg-pink-500/15 text-pink-400 border-pink-500/30";
    default: return "bg-slate-500/15 text-slate-400 border-slate-500/30";
  }
}

export function RecordingSteps({ recordings }: RecordingStepsProps) {
  if (recordings.length === 0) return <p className="text-sm text-muted-foreground text-center py-4">No recordings</p>;
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Step Recordings ({recordings.length})</CardTitle></CardHeader>
      <CardContent>
        <div className="space-y-2">
          {recordings.map((rec) => (
            <div key={rec.recording_id} className="flex items-start gap-3 p-2 rounded bg-muted/30">
              <span className="text-xs font-mono text-muted-foreground w-6 text-right shrink-0">{rec.step_number}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <Badge variant="outline" className={`text-[10px] h-4 px-1 ${actionColor(rec.action_type)}`}>{rec.action_type}</Badge>
                  {rec.duration_ms !== null && <span className="text-[10px] text-muted-foreground">{rec.duration_ms}ms</span>}
                </div>
                {rec.target && <p className="text-xs font-mono text-muted-foreground truncate">{rec.target}</p>}
                {rec.value && <p className="text-xs text-muted-foreground">→ {rec.value}</p>}
                {rec.result && <p className="text-[10px] text-green-400/80 mt-0.5">{rec.result}</p>}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
