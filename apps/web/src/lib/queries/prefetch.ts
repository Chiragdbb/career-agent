import "server-only";

import type { QueryClient } from "@tanstack/react-query";

import { fetchJsonServer } from "@/lib/fetch-json-server";
import { queryKeys } from "@/lib/query-keys";
import type { PreferenceSettings } from "@/lib/preferences";

import type {
  ApplicationRow,
  DashboardSummary,
  HumanTaskRow,
  JobMatchSummary,
  OutreachRow,
} from "@/lib/queries/options";

const STALE_MS = 30_000;

export async function prefetchWorkspaceHome(queryClient: QueryClient) {
  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: queryKeys.dashboard.summary,
      queryFn: () =>
        fetchJsonServer<DashboardSummary>("/api/v1/dashboard/summary"),
      staleTime: STALE_MS,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.preferences.settings,
      queryFn: () =>
        fetchJsonServer<{ settings: PreferenceSettings }>("/api/v1/preferences"),
      staleTime: STALE_MS,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.resumes.list,
      queryFn: () => fetchJsonServer<unknown[]>("/api/v1/resumes"),
      staleTime: STALE_MS,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.jobs.list(false),
      queryFn: () => fetchJsonServer<JobMatchSummary[]>("/api/v1/jobs"),
      staleTime: STALE_MS,
    }),
  ]);
}

export async function prefetchJobsList(
  queryClient: QueryClient,
  includeDismissed = false,
) {
  const qs = includeDismissed ? "?include_dismissed=true" : "";
  await queryClient.prefetchQuery({
    queryKey: queryKeys.jobs.list(includeDismissed),
    queryFn: () => fetchJsonServer<JobMatchSummary[]>(`/api/v1/jobs${qs}`),
    staleTime: STALE_MS,
  });
}

export async function prefetchApplicationsList(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: queryKeys.applications.list,
    queryFn: () =>
      fetchJsonServer<ApplicationRow[]>("/api/v1/applications"),
    staleTime: STALE_MS,
  });
}

export async function prefetchApprovalsBundle(queryClient: QueryClient) {
  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: queryKeys.approvals.tasks,
      queryFn: () =>
        fetchJsonServer<HumanTaskRow[]>("/api/v1/human-tasks?status=open"),
      staleTime: STALE_MS,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.approvals.outreach,
      queryFn: () => fetchJsonServer<OutreachRow[]>("/api/v1/outreach"),
      staleTime: STALE_MS,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.preferences.settings,
      queryFn: () =>
        fetchJsonServer<{ settings: PreferenceSettings }>("/api/v1/preferences"),
      staleTime: STALE_MS,
    }),
  ]);
}
