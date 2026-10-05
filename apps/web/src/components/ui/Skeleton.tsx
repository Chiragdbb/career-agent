import { cn } from "@/lib/cn";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      aria-hidden
    />
  );
}

export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 border-b border-border px-4 py-3.5 last:border-0"
        >
          <Skeleton className="h-4 w-48" />
          <Skeleton className="ml-auto h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

export function CardGridSkeleton({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-4", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border bg-card p-5">
          <Skeleton className="h-7 w-12" />
          <Skeleton className="mt-2 h-3 w-24" />
        </div>
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-72" />
      <ListSkeleton />
    </div>
  );
}

/** Full-page dossier skeleton for application / job detail views. */
export function DetailPageSkeleton() {
  return (
    <div className="animate-in fade-in space-y-6 duration-300" aria-busy="true" aria-live="polite">
      <div className="space-y-3">
        <Skeleton className="h-4 w-36 rounded-full" />
        <Skeleton className="h-9 w-2/3 max-w-md rounded-xl" />
        <Skeleton className="h-4 w-48 rounded-full" />
        <div className="flex flex-wrap gap-2 pt-1">
          <Skeleton className="h-9 w-28 rounded-full" />
          <Skeleton className="h-9 w-32 rounded-full" />
          <Skeleton className="h-9 w-28 rounded-full" />
        </div>
      </div>
      <div className="rounded-2xl border border-line bg-white p-5 shadow-card">
        <Skeleton className="mb-4 h-5 w-24" />
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="h-6 w-6 rounded-full" />
              <Skeleton className="h-4 flex-1 max-w-xs" />
            </div>
          ))}
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-2xl border border-line bg-white p-5 shadow-card">
            <Skeleton className="mb-3 h-4 w-28" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="mt-2 h-3 w-4/5" />
            <Skeleton className="mt-2 h-3 w-3/5" />
          </div>
        ))}
      </div>
    </div>
  );
}
