import { CardGridSkeleton } from "@/components/ui/Skeleton";

export default function JobsLoading() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="h-10 w-64 animate-pulse rounded-lg bg-muted" />
      <CardGridSkeleton count={4} />
    </div>
  );
}
