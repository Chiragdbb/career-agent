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

/** Dashboard / Today home: hero band + action cards + feed. */
export function TodaySkeleton() {
  return (
    <div className="animate-in fade-in space-y-8 duration-300" aria-busy="true" aria-live="polite">
      <div className="rounded-3xl border border-line bg-white/80 p-6 shadow-soft sm:p-8">
        <Skeleton className="mb-4 h-6 w-40 rounded-full" />
        <Skeleton className="h-9 w-2/3 max-w-md rounded-xl" />
        <Skeleton className="mt-2 h-8 w-1/2 max-w-sm rounded-xl" />
        <Skeleton className="mt-4 h-4 w-full max-w-xl" />
        <Skeleton className="mt-2 h-4 w-3/5 max-w-md" />
        <div className="mt-6 flex max-w-xl items-center gap-4 rounded-[32px] border border-line bg-paper p-4">
          <Skeleton className="size-16 shrink-0 rounded-full" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-3 w-48" />
          </div>
        </div>
      </div>
      <div>
        <Skeleton className="mb-4 h-6 w-48" />
        <CardGridSkeleton count={2} className="mb-0" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-6 w-36" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-3 rounded-2xl border border-line bg-white px-4 py-3.5"
          >
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 flex-1 max-w-sm" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Jobs / Opportunities list: discovery card + job rows. */
export function JobsListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="animate-in fade-in space-y-6 duration-300" aria-busy="true" aria-live="polite">
      <div className="space-y-2">
        <Skeleton className="h-9 w-48 rounded-xl" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="rounded-2xl border border-line bg-white p-5 shadow-soft sm:p-6">
        <Skeleton className="h-6 w-36" />
        <Skeleton className="mt-2 h-4 w-72" />
        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
          <Skeleton className="h-11 flex-1 rounded-2xl" />
          <Skeleton className="h-11 w-44 rounded-full" />
        </div>
      </div>
      <div className="flex items-center justify-between gap-3">
        <Skeleton className="h-6 w-28" />
        <Skeleton className="h-8 w-64 rounded-full" />
      </div>
      <ul className="space-y-4">
        {Array.from({ length: rows }).map((_, i) => (
          <li
            key={i}
            className="rounded-2xl border border-line bg-white p-5 shadow-card sm:p-6"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex min-w-0 flex-1 gap-3">
                <Skeleton className="mt-2 h-4 w-4 rounded" />
                <Skeleton className="size-12 shrink-0 rounded-2xl" />
                <div className="min-w-0 flex-1 space-y-2">
                  <Skeleton className="h-6 w-2/3 max-w-xs" />
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="mt-2 h-16 w-full rounded-2xl" />
                </div>
              </div>
              <div className="flex shrink-0 flex-col gap-2 sm:w-40">
                <Skeleton className="h-10 w-full rounded-full" />
                <Skeleton className="h-9 w-full rounded-full" />
              </div>
            </div>
          </li>
        ))}
      </ul>
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
