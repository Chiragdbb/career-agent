import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

import ApprovalsPageClient from "@/app/approvals/ApprovalsPage";
import { getQueryClient } from "@/lib/query-client";
import { prefetchApprovalsBundle } from "@/lib/queries/prefetch";

export default async function ApprovalsPage() {
  const queryClient = getQueryClient();
  try {
    await prefetchApprovalsBundle(queryClient);
  } catch {
    // Client refetch handles errors.
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <ApprovalsPageClient />
    </HydrationBoundary>
  );
}
