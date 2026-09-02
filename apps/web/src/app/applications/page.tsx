"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FileCheck } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/cn";
import { createClient } from "@/lib/supabase/client";

type Application = {
  id: string;
  job_id: string;
  status: string;
  job_title: string | null;
  company_name: string | null;
  applied_at: string | null;
};

const pipelineColumns = [
  { key: "saved", label: "Saved" },
  { key: "applied", label: "Applied" },
  { key: "screening", label: "Screening" },
  { key: "interview", label: "Interview" },
  { key: "offer", label: "Offer" },
] as const;

function columnForStatus(status: string) {
  const s = status.toLowerCase();
  if (s.includes("offer")) return "offer";
  if (s.includes("interview")) return "interview";
  if (s.includes("screen")) return "screening";
  if (s.includes("applied") || s.includes("submit")) return "applied";
  return "saved";
}

function daysInStage(appliedAt: string | null): number | null {
  if (!appliedAt) return null;
  const diff = Date.now() - new Date(appliedAt).getTime();
  return Math.floor(diff / (1000 * 60 * 60 * 24));
}

export default function ApplicationsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<Application[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"board" | "list">(
    searchParams.get("view") === "list" ? "list" : "board",
  );

  useEffect(() => {
    const v = searchParams.get("view");
    if (v === "list") setView("list");
    else if (v === "board") setView("board");
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user) {
          router.replace("/login");
          return;
        }
        const response = await apiFetch("/api/v1/applications");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setRows((await response.json()) as Application[]);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const grouped = pipelineColumns.reduce(
    (acc, col) => {
      acc[col.key] = rows.filter((r) => columnForStatus(r.status) === col.key);
      return acc;
    },
    {} as Record<string, Application[]>,
  );

  return (
    <AppShell active="applications" wide>
      <PageHeader
        title="Applications"
        serif
        actions={
          <div className="flex w-full gap-1 rounded-md bg-muted p-1 sm:w-auto">
            <button
              type="button"
              onClick={() => setView("board")}
              className={cn(
                "flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors sm:flex-none",
                view === "board"
                  ? "border border-border bg-card font-semibold text-foreground shadow-sm"
                  : "text-muted-foreground",
              )}
            >
              Board
            </button>
            <button
              type="button"
              onClick={() => setView("list")}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs transition-colors",
                view === "list"
                  ? "border border-border bg-card font-semibold text-foreground shadow-sm"
                  : "text-muted-foreground",
              )}
            >
              List
            </button>
          </div>
        }
      />

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <p className="py-8 text-sm text-muted-foreground">Loading…</p>
      ) : !loading && rows.length === 0 && !error ? (
        <EmptyState
          icon={FileCheck}
          title="No applications yet"
          description="Save a job and start an application to track your pipeline here."
          primaryActionLabel="Browse jobs"
          actionHref="/jobs"
        />
      ) : view === "board" ? (
        <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-4 md:snap-none">
          {pipelineColumns.map((col) => (
            <div
              key={col.key}
              className="flex min-w-[85vw] flex-1 snap-center flex-col gap-2 rounded-lg bg-muted p-3 sm:min-w-[200px] md:min-w-[200px]"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground">
                  {col.label}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {grouped[col.key]?.length ?? 0}
                </span>
              </div>
              {(grouped[col.key] ?? []).map((row) => {
                const days = daysInStage(row.applied_at);
                const stale = days != null && days > 10;
                return (
                <Link
                  key={row.id}
                  href={`/applications/${row.id}`}
                  className="rounded-lg border border-line bg-paper-raised p-3 transition-shadow hover:shadow-sm"
                >
                  <p className="text-xs font-semibold text-ink">
                    {row.job_title || "Untitled role"}
                  </p>
                  <p className="mt-1 text-[11px] text-text-muted">
                    {row.company_name}
                  </p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <Badge variant="primary" className="text-[10px]">
                      {row.status}
                    </Badge>
                    {days != null ? (
                      <span
                        className={cn(
                          "text-[10px]",
                          stale ? "font-medium text-brick" : "text-text-faint",
                        )}
                      >
                        {days}d in stage{stale ? " · stale" : ""}
                      </span>
                    ) : null}
                  </div>
                </Link>
              );})}
              {(grouped[col.key] ?? []).length === 0 ? (
                <p className="py-4 text-center text-[11px] text-muted-foreground">Empty</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <ul>
            {rows.map((row) => (
              <li key={row.id} className="border-b border-border last:border-0">
                <Link
                  href={`/applications/${row.id}`}
                  className="flex items-center justify-between px-4 py-3 hover:bg-muted/30"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {row.job_title || "Untitled role"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {[row.company_name, row.status].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <Badge variant="default">{row.status}</Badge>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </AppShell>
  );
}
