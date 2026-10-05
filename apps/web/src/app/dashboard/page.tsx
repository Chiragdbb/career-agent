import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

import DashboardClient from "@/app/dashboard/DashboardClient";
import { getQueryClient } from "@/lib/query-client";
import { prefetchWorkspaceHome } from "@/lib/queries/prefetch";

export default async function DashboardPage() {
  const queryClient = getQueryClient();
  try {
    await prefetchWorkspaceHome(queryClient);
  } catch {
    // Client will surface auth/API errors after hydration.
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DashboardClient />
    </HydrationBoundary>
  );
}
