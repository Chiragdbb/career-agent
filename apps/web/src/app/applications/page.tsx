import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

import ApplicationsPageClient from "@/app/applications/ApplicationsPage";
import { getQueryClient } from "@/lib/query-client";
import { prefetchApplicationsList } from "@/lib/queries/prefetch";

export default async function ApplicationsPage() {
  const queryClient = getQueryClient();
  try {
    await prefetchApplicationsList(queryClient);
  } catch {
    // Client refetch handles errors.
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <ApplicationsPageClient />
    </HydrationBoundary>
  );
}
