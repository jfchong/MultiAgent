import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { RequestInput } from "@/components/requests/RequestInput";
import { RequestHistory } from "@/components/requests/RequestHistory";
import type { RequestListResponse } from "@/types";

export default function RequestsPage() {
  const { data, refresh } = usePolling<RequestListResponse>(
    () => api.get<RequestListResponse>("/api/requests?limit=50&offset=0"), 5000
  );
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Requests</h1>
        <p className="text-sm text-muted-foreground">Submit work to the Ultra Agent system</p>
      </div>
      <RequestInput onSubmitted={refresh} />
      <RequestHistory data={data} />
    </div>
  );
}
