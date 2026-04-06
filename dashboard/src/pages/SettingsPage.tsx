import { useState } from "react";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Trash2, Save, Plus, Loader2 } from "lucide-react";
import { timeAgo } from "@/lib/format";
import type { ConfigItem, CredentialItem, CronJob } from "@/types";

// ---------------------------------------------------------------------------
// Configuration Tab
// ---------------------------------------------------------------------------

function ConfigurationTab() {
  const { data: configs, loading, refresh } = usePolling<ConfigItem[]>(
    () => api.get<ConfigItem[]>("/api/config"),
    10000
  );

  // editMap: key -> current draft value (undefined = not editing)
  const [editMap, setEditMap] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  function startEdit(key: string, currentValue: string) {
    setEditMap((prev) => ({ ...prev, [key]: currentValue }));
    setSaveError(null);
  }

  function cancelEdit(key: string) {
    setEditMap((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  async function saveEdit(key: string) {
    const newValue = editMap[key];
    if (newValue === undefined) return;
    setSavingKey(key);
    setSaveError(null);
    try {
      await api.put(`/api/config/${encodeURIComponent(key)}`, { value: newValue });
      cancelEdit(key);
      refresh();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingKey(null);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent, key: string) {
    if (e.key === "Enter") saveEdit(key);
    if (e.key === "Escape") cancelEdit(key);
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Configuration</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {loading && (
          <div className="px-4 py-6 space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-10 bg-muted rounded animate-pulse" />
            ))}
          </div>
        )}
        {saveError && (
          <p className="mx-4 mt-2 text-xs text-red-400">{saveError}</p>
        )}
        {configs && configs.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-6">No config items</p>
        )}
        {configs && configs.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-1/3">Key</TableHead>
                <TableHead>Value</TableHead>
                <TableHead className="w-24 text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {configs.map((item) => {
                const isEditing = editMap[item.key] !== undefined;
                const isSaving = savingKey === item.key;
                return (
                  <TableRow key={item.key}>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {item.key}
                    </TableCell>
                    <TableCell>
                      {isEditing ? (
                        <Input
                          value={editMap[item.key]}
                          autoFocus
                          className="h-7 text-xs"
                          onChange={(e) =>
                            setEditMap((prev) => ({ ...prev, [item.key]: e.target.value }))
                          }
                          onKeyDown={(e) => handleKeyDown(e, item.key)}
                          disabled={isSaving}
                        />
                      ) : (
                        <span
                          className="text-sm cursor-pointer hover:text-foreground text-muted-foreground transition-colors"
                          title="Click to edit"
                          onClick={() => startEdit(item.key, item.value)}
                        >
                          {item.value || <span className="italic opacity-50">empty</span>}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {isEditing ? (
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 px-2 text-xs"
                            onClick={() => cancelEdit(item.key)}
                            disabled={isSaving}
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={() => saveEdit(item.key)}
                            disabled={isSaving}
                          >
                            {isSaving ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Save className="h-3 w-3" />
                            )}
                            Save
                          </Button>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2 text-xs"
                          onClick={() => startEdit(item.key, item.value)}
                        >
                          Edit
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Credentials Tab
// ---------------------------------------------------------------------------

type AuthType = "password" | "oauth" | "api_key" | "cookie";

function CredentialsTab() {
  const { data: credentials, loading, refresh } = usePolling<CredentialItem[]>(
    () => api.get<CredentialItem[]>("/api/credentials"),
    10000
  );

  const [domain, setDomain] = useState("");
  const [label, setLabel] = useState("");
  const [authType, setAuthType] = useState<AuthType>("password");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [confirmDelete, setConfirmDelete] = useState<CredentialItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleAdd() {
    if (!domain.trim() || !label.trim()) {
      setAddError("Domain and label are required.");
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      await api.post("/api/credentials", {
        site_domain: domain.trim(),
        label: label.trim(),
        auth_type: authType,
      });
      setDomain("");
      setLabel("");
      setAuthType("password");
      refresh();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Add failed");
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete() {
    if (!confirmDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.delete(`/api/credentials/${encodeURIComponent(confirmDelete.credential_id)}`);
      setConfirmDelete(null);
      refresh();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      {/* Add form */}
      <Card className="mb-4">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Add Credential</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 items-end">
            <div className="flex-1 min-w-36">
              <label className="text-xs text-muted-foreground mb-1 block">Domain</label>
              <Input
                placeholder="example.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="h-8 text-sm"
                disabled={adding}
              />
            </div>
            <div className="flex-1 min-w-36">
              <label className="text-xs text-muted-foreground mb-1 block">Label</label>
              <Input
                placeholder="Main account"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="h-8 text-sm"
                disabled={adding}
              />
            </div>
            <div className="w-36">
              <label className="text-xs text-muted-foreground mb-1 block">Auth Type</label>
              <Select
                value={authType}
                onValueChange={(v) => setAuthType(v as AuthType)}
                disabled={adding}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="password">Password</SelectItem>
                  <SelectItem value="oauth">OAuth</SelectItem>
                  <SelectItem value="api_key">API Key</SelectItem>
                  <SelectItem value="cookie">Cookie</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button size="sm" className="h-8" onClick={handleAdd} disabled={adding}>
              {adding ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Plus className="h-3 w-3 mr-1" />}
              Add
            </Button>
          </div>
          {addError && <p className="text-xs text-red-400 mt-2">{addError}</p>}
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Stored Credentials</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading && (
            <div className="px-4 py-6 space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-muted rounded animate-pulse" />
              ))}
            </div>
          )}
          {credentials && credentials.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-6">No credentials stored</p>
          )}
          {credentials && credentials.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Domain</TableHead>
                  <TableHead>Label</TableHead>
                  <TableHead className="w-28">Auth Type</TableHead>
                  <TableHead className="w-28">Created</TableHead>
                  <TableHead className="w-16 text-right">Delete</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {credentials.map((cred) => (
                  <TableRow key={cred.credential_id}>
                    <TableCell className="font-mono text-xs">{cred.site_domain}</TableCell>
                    <TableCell className="text-sm">{cred.label}</TableCell>
                    <TableCell>
                      <span className="text-xs bg-muted rounded px-1.5 py-0.5">{cred.auth_type}</span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {timeAgo(cred.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-muted-foreground hover:text-red-400"
                        onClick={() => { setConfirmDelete(cred); setDeleteError(null); }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Confirm delete dialog */}
      <Dialog open={!!confirmDelete} onOpenChange={(open) => { if (!open) setConfirmDelete(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Credential</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete the credential for{" "}
            <span className="font-mono text-foreground">{confirmDelete?.site_domain}</span>?
            This cannot be undone.
          </p>
          {deleteError && <p className="text-xs text-red-400">{deleteError}</p>}
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmDelete(null)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Trash2 className="h-3 w-3 mr-1" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Cron Jobs Tab
// ---------------------------------------------------------------------------

function CronJobsTab() {
  const { data: jobs, loading, refresh } = usePolling<CronJob[]>(
    () => api.get<CronJob[]>("/api/cron"),
    10000
  );

  const [agentId, setAgentId] = useState("");
  const [expression, setExpression] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [confirmDelete, setConfirmDelete] = useState<CronJob | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleAdd() {
    if (!agentId.trim() || !expression.trim()) {
      setAddError("Agent ID and cron expression are required.");
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      await api.post("/api/cron", {
        agent_id: agentId.trim(),
        cron_expression: expression.trim(),
      });
      setAgentId("");
      setExpression("");
      refresh();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Add failed");
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete() {
    if (!confirmDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.delete(`/api/cron/${encodeURIComponent(confirmDelete.schedule_id)}`);
      setConfirmDelete(null);
      refresh();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      {/* Add form */}
      <Card className="mb-4">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Add Cron Job</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 items-end">
            <div className="flex-1 min-w-40">
              <label className="text-xs text-muted-foreground mb-1 block">Agent ID</label>
              <Input
                placeholder="executor"
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                className="h-8 text-sm"
                disabled={adding}
              />
            </div>
            <div className="flex-1 min-w-40">
              <label className="text-xs text-muted-foreground mb-1 block">Cron Expression</label>
              <Input
                placeholder="*/5 * * * *"
                value={expression}
                onChange={(e) => setExpression(e.target.value)}
                className="h-8 text-sm font-mono"
                disabled={adding}
              />
            </div>
            <Button size="sm" className="h-8" onClick={handleAdd} disabled={adding}>
              {adding ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Plus className="h-3 w-3 mr-1" />}
              Add
            </Button>
          </div>
          {addError && <p className="text-xs text-red-400 mt-2">{addError}</p>}
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Scheduled Jobs</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading && (
            <div className="px-4 py-6 space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-muted rounded animate-pulse" />
              ))}
            </div>
          )}
          {jobs && jobs.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-6">No cron jobs configured</p>
          )}
          {jobs && jobs.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead className="w-36">Expression</TableHead>
                  <TableHead className="w-20">Enabled</TableHead>
                  <TableHead className="w-16 text-right">Fires</TableHead>
                  <TableHead className="w-28">Last Fired</TableHead>
                  <TableHead className="w-28">Next Fire</TableHead>
                  <TableHead className="w-16 text-right">Delete</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.schedule_id}>
                    <TableCell className="text-sm">
                      {job.agent_name || job.agent_id}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{job.cron_expression}</TableCell>
                    <TableCell>
                      <span
                        className={`text-xs rounded px-1.5 py-0.5 ${
                          job.is_enabled
                            ? "bg-green-500/15 text-green-400"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {job.is_enabled ? "Yes" : "No"}
                      </span>
                    </TableCell>
                    <TableCell className="text-right text-sm">{job.fire_count}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {job.last_fired_at ? timeAgo(job.last_fired_at) : "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {job.next_fire_at ? timeAgo(job.next_fire_at) : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-muted-foreground hover:text-red-400"
                        onClick={() => { setConfirmDelete(job); setDeleteError(null); }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Confirm delete dialog */}
      <Dialog open={!!confirmDelete} onOpenChange={(open) => { if (!open) setConfirmDelete(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Cron Job</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete the cron job for agent{" "}
            <span className="font-mono text-foreground">
              {confirmDelete?.agent_name || confirmDelete?.agent_id}
            </span>{" "}
            with expression{" "}
            <span className="font-mono text-foreground">{confirmDelete?.cron_expression}</span>?
          </p>
          {deleteError && <p className="text-xs text-red-400">{deleteError}</p>}
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmDelete(null)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Trash2 className="h-3 w-3 mr-1" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">
          System configuration, credentials, and scheduled jobs
        </p>
      </div>

      <Tabs defaultValue="config">
        <TabsList className="mb-4">
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="credentials">Credentials</TabsTrigger>
          <TabsTrigger value="cron">Cron Jobs</TabsTrigger>
        </TabsList>

        <TabsContent value="config">
          <ConfigurationTab />
        </TabsContent>

        <TabsContent value="credentials">
          <CredentialsTab />
        </TabsContent>

        <TabsContent value="cron">
          <CronJobsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
