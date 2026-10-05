import { CardGridSkeleton } from "@/components/ui/Skeleton";

export default function ApplicationsLoading() {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="h-10 w-56 animate-pulse rounded-lg bg-muted" />
      <CardGridSkeleton count={3} />
    </div>
  );
}
