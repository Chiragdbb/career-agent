import { fetchJsonClient } from "@/lib/fetch-json-client";
import { queryKeys } from "@/lib/query-keys";
import type { PreferenceSettings } from "@/lib/preferences";

export type DashboardSummary = {
  jobs_count: number;
  applications_count: number;
  open_human_tasks: number;
  preparing_pipelines?: number;
  failed_pipelines?: number;
  unread_notifications: number;
  upcoming_interviews: number;
  pending_offers: number;
  open_follow_ups: number;
};

export type JobMatchSummary = {
  id: string;
  job_id: string;
  status: string;
  score: number | null;
  title: string;
  company_name: string | null;
  location: string | null;
  work_arrangement: string | null;
  url: string | null;
  is_new?: boolean;
  application_id?: string | null;
  rationale?: string | null;
};

export type ApplicationRow = {
  id: string;
  job_id: string;
  status: string;
  job_title: string | null;
  company_name: string | null;
  applied_at: string | null;
};

export type HumanTaskRow = {
  id: string;
  task_type: string;
  title: string | null;
  status: string;
  details: Record<string, unknown>;
  application_id: string | null;
  outreach_id: string | null;
};

export type OutreachRow = {
  id: string;
  contact_id: string;
  status: string;
  subject: string | null;
  body?: string | null;
  reason?: string | null;
};

const STALE_MS = 30_000;

export function dashboardSummaryQueryOptions() {
  return {
    queryKey: queryKeys.dashboard.summary,
    queryFn: () => fetchJsonClient<DashboardSummary>("/api/v1/dashboard/summary"),
    staleTime: STALE_MS,
  };
}

export function preferencesQueryOptions() {
  return {
    queryKey: queryKeys.preferences.settings,
    queryFn: () =>
      fetchJsonClient<{ settings: PreferenceSettings }>("/api/v1/preferences"),
    staleTime: STALE_MS,
  };
}

export function resumesListQueryOptions() {
  return {
    queryKey: queryKeys.resumes.list,
    queryFn: () => fetchJsonClient<unknown[]>("/api/v1/resumes"),
    staleTime: STALE_MS,
  };
}

export function jobsListQueryOptions(includeDismissed: boolean) {
  const qs = includeDismissed ? "?include_dismissed=true" : "";
  return {
    queryKey: queryKeys.jobs.list(includeDismissed),
    queryFn: () => fetchJsonClient<JobMatchSummary[]>(`/api/v1/jobs${qs}`),
    staleTime: STALE_MS,
  };
}

export function applicationsListQueryOptions() {
  return {
    queryKey: queryKeys.applications.list,
    queryFn: () => fetchJsonClient<ApplicationRow[]>("/api/v1/applications"),
    staleTime: STALE_MS,
  };
}

export function approvalsTasksQueryOptions() {
  return {
    queryKey: queryKeys.approvals.tasks,
    queryFn: () =>
      fetchJsonClient<HumanTaskRow[]>("/api/v1/human-tasks?status=open"),
    staleTime: STALE_MS,
  };
}

export function approvalsOutreachQueryOptions() {
  return {
    queryKey: queryKeys.approvals.outreach,
    queryFn: () => fetchJsonClient<OutreachRow[]>("/api/v1/outreach"),
    staleTime: STALE_MS,
  };
}
