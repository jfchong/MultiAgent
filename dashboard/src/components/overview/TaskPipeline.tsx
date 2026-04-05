import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface PipelineData {
  pending: number;
  assigned: number;
  awaiting_release: number;
  in_progress: number;
  completed: number;
  failed: number;
}

interface TaskPipelineProps {
  data: PipelineData | null;
}

const stages = [
  { key: "pending" as const, label: "Pending", color: "bg-slate-500" },
  { key: "assigned" as const, label: "Assigned", color: "bg-blue-500" },
  { key: "awaiting_release" as const, label: "Awaiting", color: "bg-amber-500" },
  { key: "in_progress" as const, label: "In Progress", color: "bg-blue-400" },
  { key: "completed" as const, label: "Completed", color: "bg-green-500" },
  { key: "failed" as const, label: "Failed", color: "bg-red-500" },
];

export function TaskPipeline({ data }: TaskPipelineProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Task Pipeline</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2">
          {stages.map((stage, idx) => (
            <div key={stage.key} className="flex items-center">
              {idx > 0 && (
                <div className="w-4 h-px bg-border mx-1" />
              )}
              <div className="flex flex-col items-center min-w-[70px]">
                <div
                  className={`${stage.color} text-white rounded-md px-3 py-2 text-center w-full transition-all`}
                >
                  <span className="text-lg font-bold block">
                    {data ? data[stage.key] : "-"}
                  </span>
                </div>
                <span className="text-[10px] text-muted-foreground mt-1 whitespace-nowrap">
                  {stage.label}
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
