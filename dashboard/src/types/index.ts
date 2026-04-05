// ---- System ----
export interface StatusData {
  running_agents: number;
  total_agents: number;
  pending_tasks: number;
  assigned_tasks: number;
  pending_releases: number;
  active_rules: number;
  completed_today: number;
  success_rate: number;
  tasks_by_status: Record<string, number>;
}

// ---- Tasks ----
export type TaskStatus =
  | "pending" | "assigned" | "in_progress" | "awaiting_release"
  | "blocked" | "review" | "completed" | "failed" | "cancelled";

export interface TaskSummary {
  task_id: string;
  parent_task_id: string | null;
  title: string;
  status: TaskStatus;
  priority: number;
  assigned_agent: string | null;
  agent_name: string | null;
  created_by: string | null;
  framework: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface TaskDetail extends TaskSummary {
  description: string | null;
  toolkits_json: string | null;
  input_data: string | null;
  output_data: string | null;
  error_message: string | null;
  depends_on_json: string | null;
  updated_at: string | null;
  deadline: string | null;
  retry_count: number;
  max_retries: number;
}

export interface TaskListResponse { items: TaskSummary[]; total: number; }
export interface TimelineEvent { event_id: string; event_type: string; agent_id: string | null; agent_name: string | null; data_json: string; created_at: string; }
export interface SubtaskNode { task_id: string; title: string; status: TaskStatus; assigned_agent: string | null; agent_name: string | null; priority: number; created_at: string; completed_at: string | null; children: SubtaskNode[]; }

// ---- Requests ----
export interface RequestItem { task_id: string; title: string; description: string | null; status: TaskStatus; priority: number; created_at: string; completed_at: string | null; output_data: string | null; subtask_count: number; completed_subtask_count: number; }
export interface RequestListResponse { items: RequestItem[]; total: number; }

// ---- Agents ----
export interface AgentSummary { agent_id: string; agent_name: string; agent_type: string; level: number; parent_agent_id: string | null; status: string; run_count: number; error_count: number; last_run_at: string | null; active_task_count: number; success_rate: number; }
export interface AgentDetail extends AgentSummary { prompt_file: string | null; skill_id: string | null; sub_agent_role: string | null; config_json: string | null; session_id: string | null; current_task: { task_id: string; title: string; status: string } | null; recent_tasks: TaskSummary[]; }
export interface AgentHierarchyNode extends AgentSummary { children: AgentHierarchyNode[]; }
export interface AgentSession { session_id: string; task_id: string | null; task_title: string | null; browser_category: string | null; status: string; success: number; started_at: string; completed_at: string | null; duration_seconds: number | null; summary: string | null; }

// ---- Releases ----
export interface ReleaseItem { release_id: string; task_id: string; agent_id: string; agent_level: number; title: string; description: string | null; action_type: string; input_preview: string | null; output_preview: string | null; status: string; auto_release: number; auto_release_rule_id: string | null; reviewed_at: string | null; created_at: string; agent_name?: string; task_title?: string; }
export interface ReleaseListResponse { items: ReleaseItem[]; total: number; }
export interface AutoReleaseRule { rule_id: string; match_agent_type: string | null; match_action_type: string | null; match_skill_id: string | null; match_title_pattern: string | null; is_enabled: number; created_from_release_id: string | null; fire_count: number; created_at: string; }
