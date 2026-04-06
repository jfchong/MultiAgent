import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";

interface StatusData {
  running_agents: number;
  total_agents: number;
  pending_tasks: number;
  assigned_tasks: number;
  pending_releases: number;
  active_rules: number;
  completed_today: number;
  success_rate: number;
}

interface KpiCardsProps {
  data: StatusData | null;
}

export function KpiCards({ data }: KpiCardsProps) {
  const navigate = useNavigate();

  if (!data) {
    return (
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-4">
              <div className="h-4 w-24 bg-muted rounded mb-3" />
              <div className="h-8 w-16 bg-muted rounded mb-2" />
              <div className="h-3 w-20 bg-muted rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    {
      label: "Running Agents",
      value: data.running_agents,
      secondary: `of ${data.total_agents} total`,
      borderColor: "border-l-blue-500",
      onClick: () => navigate("/agents"),
    },
    {
      label: "Pending Tasks",
      value: data.pending_tasks,
      secondary: `${data.assigned_tasks} assigned`,
      borderColor: "border-l-amber-500",
      onClick: () => navigate("/tasks?status=pending"),
    },
    {
      label: "Awaiting Review",
      value: data.pending_releases,
      secondary: `${data.active_rules} rules active`,
      borderColor: "border-l-purple-500",
      onClick: () => navigate("/releases"),
    },
    {
      label: "Completed Today",
      value: data.completed_today,
      secondary: `${Math.round(data.success_rate * 100)}% success rate`,
      borderColor: "border-l-green-500",
      onClick: () => navigate("/tasks?status=completed"),
    },
  ];

  return (
    <div className="grid grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card
          key={card.label}
          className={`border-l-4 ${card.borderColor} cursor-pointer transition-colors hover:bg-accent/50`}
          onClick={card.onClick}
        >
          <CardContent className="p-4">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {card.label}
            </p>
            <p className="text-3xl font-bold text-foreground mt-1">{card.value}</p>
            <p className="text-xs text-muted-foreground mt-1">{card.secondary}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
