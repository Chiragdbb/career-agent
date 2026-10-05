import { CardGridSkeleton } from "@/components/ui/Skeleton";

export default function DashboardLoading() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="h-24 animate-pulse rounded-3xl bg-muted" />
      <CardGridSkeleton count={2} />
    </div>
  );
}
