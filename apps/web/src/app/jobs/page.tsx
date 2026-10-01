import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

import JobsPage from "@/app/jobs/JobsPage";
import { getQueryClient } from "@/lib/query-client";
import { prefetchJobsList } from "@/lib/queries/prefetch";

export default async function JobsRoutePage() {
  const queryClient = getQueryClient();
  try {
    await prefetchJobsList(queryClient, false);
  } catch {
    // Client refetch handles errors.
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <JobsPage />
    </HydrationBoundary>
  );
}
