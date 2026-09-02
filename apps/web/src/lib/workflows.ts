import { apiFetch } from "@/lib/api";

export type WorkflowRun = {
  id: string;
  workflow_type: string;
  status: string;
  error: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
  task_count: number;
  completed_task_count: number;
  failed_task_count: number;
};

export type WorkflowTask = {
  id: string;
  workflow_run_id: string;
  task_type: string;
  status: string;
  input_payload: Record<string, unknown> | null;
  output_payload: Record<string, unknown> | null;
  error: string | null;
  attempt: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ActivityEvent = {
  id: string;
  type: string;
  message: string;
  timestamp: Date;
  phase?: string;
  step?: string;
  detail?: string;
  payload?: Record<string, unknown>;
};

export function formatEventDetail(payload?: Record<string, unknown>): string | null {
  if (!payload) return null;
  const data = (payload.data as Record<string, unknown>) || payload;
  const parts: string[] = [];
  if (payload.step) parts.push(`step: ${String(payload.step)}`);
  if (payload.phase) parts.push(`phase: ${String(payload.phase)}`);
  if (data.provider) parts.push(`provider: ${String(data.provider)}`);
  if (data.query) parts.push(`query: “${String(data.query)}”`);
  if (data.url) parts.push(`url: ${String(data.url)}`);
  if (data.title) parts.push(`title: ${String(data.title)}`);
  if (data.company) parts.push(`company: ${String(data.company)}`);
  if (data.content_source) parts.push(`source: ${String(data.content_source)}`);
  if (data.fallback) parts.push(`fallback: ${String(data.fallback)}`);
  if (data.error) parts.push(`error: ${String(data.error)}`);
  if (data.created_count != null) parts.push(`new: ${String(data.created_count)}`);
  if (data.duplicate_count != null) parts.push(`existing: ${String(data.duplicate_count)}`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

const ACTIVE_STATUSES = new Set(["queued", "running", "cancelling"]);

export function isActiveWorkflow(status: string): boolean {
  return ACTIVE_STATUSES.has(status.toLowerCase());
}

export function workflowStatusVariant(
  status: string,
): "default" | "success" | "warning" | "error" | "primary" {
  const s = status.toLowerCase();
  if (s === "completed") return "success";
  if (s === "failed" || s === "cancelled") return "error";
  if (s === "running" || s === "cancelling") return "primary";
  if (s === "queued") return "warning";
  return "default";
}

export function formatWorkflowType(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatEventMessage(
  type: string,
  payload?: Record<string, unknown>,
): string {
  switch (type) {
    case "workflow_progress":
      return (
        (payload?.message as string) ||
        `Step: ${(payload?.step as string) || "processing"}`
      );
    case "workflow_completed":
      return `Workflow completed (${payload?.workflow_type || "process"})`;
    case "workflow_cancelled":
      return `Discovery cancelled${payload?.created_count != null ? ` (${payload.created_count} jobs saved)` : ""}`;
    case "jobs_discovered": {
      const created = payload?.created_count ?? 0;
      const dupes = payload?.duplicate_count ?? 0;
      return `Discovery finished: ${created} new, ${dupes} existing`;
    }
    case "workflow_failed":
      return `Workflow failed: ${(payload?.error as string) || "unknown error"}`;
    case "human_task_created":
      return "Automation paused — your input is needed";
    case "notification_created":
      return (payload?.title as string) || "New notification";
    case "application_state_changed":
      return `Application updated: ${(payload?.status as string) || ""}`;
    case "research_completed":
      return "Company research completed";
    case "resume_ready":
      return "Resume draft is ready";
    case "email_sent":
      return "Email sent";
    case "follow_up_due":
      return "Follow-up is due";
    case "interview_scheduled":
      return "Interview scheduled";
    case "offer_updated":
      return "Offer updated";
    default:
      return type.replace(/_/g, " ");
  }
}

export async function cancelWorkflowRun(runId: string): Promise<WorkflowRun> {
  const response = await apiFetch(`/api/v1/workflows/${runId}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `API ${response.status}`);
  }
  return (await response.json()) as WorkflowRun;
}

export async function fetchWorkflowRuns(options?: {
  activeOnly?: boolean;
  limit?: number;
}): Promise<WorkflowRun[]> {
  const params = new URLSearchParams();
  if (options?.activeOnly) params.set("active_only", "true");
  if (options?.limit) params.set("limit", String(options.limit));
  const qs = params.toString();
  const response = await apiFetch(`/api/v1/workflows${qs ? `?${qs}` : ""}`);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `API ${response.status}`);
  }
  return (await response.json()) as WorkflowRun[];
}

export async function fetchWorkflowRun(runId: string): Promise<WorkflowRun> {
  const response = await apiFetch(`/api/v1/workflows/${runId}`);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `API ${response.status}`);
  }
  return (await response.json()) as WorkflowRun;
}

export async function fetchWorkflowTasks(runId: string): Promise<WorkflowTask[]> {
  const response = await apiFetch(`/api/v1/workflows/${runId}/tasks`);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `API ${response.status}`);
  }
  return (await response.json()) as WorkflowTask[];
}
