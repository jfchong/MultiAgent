import { Badge } from "@/components/ui/badge";
import { statusColor } from "@/lib/format";

interface StatusBadgeProps { status: string; className?: string; }

export function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const label = status.replace(/_/g, " ");
  return (
    <Badge variant="outline" className={`text-[10px] font-medium capitalize ${statusColor(status)} ${className}`}>
      {label}
    </Badge>
  );
}
