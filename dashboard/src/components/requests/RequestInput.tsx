import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Send, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface RequestInputProps { onSubmitted: () => void; }

export function RequestInput({ onSubmitted }: RequestInputProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("5");
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setSubmitting(true);
    setFeedback(null);
    try {
      const result = await api.post<{ ok: boolean; task_id: string }>("/api/requests", {
        title: title.trim(),
        description: description.trim() || null,
        priority: parseInt(priority, 10),
      });
      setFeedback({ ok: true, message: `Request submitted — Task ${result.task_id.slice(0, 8)}` });
      setTitle("");
      setDescription("");
      setPriority("5");
      onSubmitted();
    } catch (err) {
      setFeedback({ ok: false, message: err instanceof Error ? err.message : "Failed to submit" });
    } finally {
      setSubmitting(false);
      setTimeout(() => setFeedback(null), 4000);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">New Request</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input placeholder="What do you need done?" value={title} onChange={(e) => setTitle(e.target.value)} disabled={submitting} />
          <Textarea placeholder="Details (optional) — describe the task, constraints, expected outcome..." value={description} onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDescription(e.target.value)} disabled={submitting} rows={3} className="resize-none" />
          <div className="flex items-center gap-3">
            <Select value={priority} onValueChange={setPriority} disabled={submitting}>
              <SelectTrigger className="w-40"><SelectValue placeholder="Priority" /></SelectTrigger>
              <SelectContent>
                {[1,2,3,4,5,6,7,8,9,10].map((p) => (
                  <SelectItem key={p} value={String(p)}>P{p} {p<=2?"— Critical":p<=4?"— High":p<=6?"— Medium":"— Low"}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button type="submit" disabled={submitting || !title.trim()} className="ml-auto">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Send className="h-4 w-4 mr-1" />}
              Submit
            </Button>
          </div>
          {feedback && <p className={`text-xs ${feedback.ok ? "text-green-400" : "text-red-400"}`}>{feedback.message}</p>}
        </form>
      </CardContent>
    </Card>
  );
}
