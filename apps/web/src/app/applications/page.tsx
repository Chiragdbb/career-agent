"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FileCheck, ShieldCheck } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ActionCard } from "@/components/ui/ActionCard";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { HeroBand } from "@/components/ui/HeroBand";
import { GoldButton } from "@/components/ui/Button";
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
  { key: "vetted", label: "Vetted", hint: "Discovered & matched" },
  { key: "signoff", label: "Sign-off", hint: "Your stamp" },
  { key: "motion", label: "In Motion", hint: "Applied" },
  { key: "interview", label: "Interviewing", hint: "Rounds ahead" },
  { key: "offer", label: "Offer Stage", hint: "Deliberation" },
] as const;

function columnForStatus(status: string) {
  const s = status.toLowerCase();
  if (s.includes("offer")) return "offer";
  if (s.includes("interview")) return "interview";
  if (s.includes("screen") || s.includes("applied") || s.includes("submit")) {
    return "motion";
  }
  if (
    s.includes("draft") ||
    s.includes("ready") ||
    s.includes("pending") ||
    s.includes("review")
  ) {
    return "signoff";
  }
  return "vetted";
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
      <HeroBand className="mb-8">
        <div className="grid gap-6 lg:grid-cols-12 lg:items-end">
          <div className="lg:col-span-8">
            <SoftBadge tone="lavender" className="mb-3">
              Active opportunities
            </SoftBadge>
            <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              Your career trajectory,{" "}
              <span className="font-serif italic text-coral">unfolded.</span>
            </h1>
            <p className="mt-3 max-w-xl text-sm text-text-muted">
              Track every stage with human control. Submissions only happen when
              you have evidence and choose to proceed.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {(
                [
                  ["board", "Visual Journey"],
                  ["list", "Compact Table"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setView(id)}
                  className={cn(
                    "rounded-full px-3.5 py-1.5 text-xs font-semibold",
                    view === id
                      ? "bg-lavender text-lavender-deep"
                      : "bg-white/70 text-text-muted",
                  )}
                >
                  {label}
                </button>
              ))}
              <Link
                href="/activity"
                className="rounded-full bg-white/70 px-3.5 py-1.5 text-xs font-semibold text-text-muted hover:text-ink"
              >
                Activity Log
              </Link>
            </div>
          </div>
          <ActionCard className="lg:col-span-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
              Stage health
            </p>
            <p className="mt-1 text-3xl font-bold text-ink">{rows.length}</p>
            <p className="text-xs text-text-muted">applications in motion</p>
          </ActionCard>
        </div>
      </HeroBand>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <p className="py-8 text-sm text-text-muted">Loading…</p>
      ) : rows.length === 0 && !error ? (
        <EmptyState
          icon={FileCheck}
          title="No applications yet"
          description="Save a job and start an application to track your pipeline here."
          primaryActionLabel="Browse opportunities"
          actionHref="/jobs"
        />
      ) : view === "board" ? (
        <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-4">
          {pipelineColumns.map((col) => (
            <div
              key={col.key}
              className={cn(
                "flex min-w-[85vw] flex-1 snap-center flex-col gap-2 rounded-3xl border border-line bg-white p-3 shadow-soft sm:min-w-[220px]",
                col.key === "signoff" && "border-coral/30 bg-coral-bg/30",
              )}
            >
              <div className="px-1 pb-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-ink">{col.label}</span>
                  <span className="text-[11px] font-semibold text-text-faint">
                    {grouped[col.key]?.length ?? 0}
                  </span>
                </div>
                <p className="text-[10px] text-text-faint">{col.hint}</p>
              </div>
              {(grouped[col.key] ?? []).map((row) => {
                const days = daysInStage(row.applied_at);
                const stale = days != null && days > 10;
                const initial = (row.company_name || "?").charAt(0);
                return (
                  <Link
                    key={row.id}
                    href={`/applications/${row.id}`}
                    className="rounded-2xl border border-line bg-white p-3 transition-shadow hover:shadow-soft"
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <span className="flex size-8 items-center justify-center rounded-xl bg-lavender text-xs font-bold text-lavender-deep">
                        {initial}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-xs font-bold text-ink">
                          {row.job_title || "Untitled role"}
                        </p>
                        <p className="truncate text-[11px] text-text-muted">
                          {row.company_name}
                        </p>
                      </div>
                    </div>
                    {col.key === "signoff" ? (
                      <SoftBadge tone="coral" className="mb-2">
                        Your stamp required
                      </SoftBadge>
                    ) : (
                      <SoftBadge tone="lavender" className="mb-2">
                        {row.status}
                      </SoftBadge>
                    )}
                    {days != null ? (
                      <p
                        className={cn(
                          "text-[10px]",
                          stale ? "font-medium text-brick" : "text-text-faint",
                        )}
                      >
                        Day {days}
                        {stale ? " · needs attention" : ""}
                      </p>
                    ) : null}
                    {col.key === "signoff" ? (
                      <span className="mt-2 inline-block text-[11px] font-bold text-coral">
                        Inspect &amp; approve →
                      </span>
                    ) : null}
                  </Link>
                );
              })}
              {(grouped[col.key] ?? []).length === 0 ? (
                <p className="py-6 text-center text-[11px] text-text-faint">
                  Empty
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-3xl border border-line bg-white shadow-soft">
          <ul>
            {rows.map((row) => (
              <li key={row.id} className="border-b border-line last:border-0">
                <Link
                  href={`/applications/${row.id}`}
                  className="flex items-center justify-between px-4 py-3.5 hover:bg-paper"
                >
                  <div>
                    <p className="text-sm font-semibold text-ink">
                      {row.job_title || "Untitled role"}
                    </p>
                    <p className="text-xs text-text-muted">
                      {[row.company_name, row.status].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <SoftBadge tone="lavender">{row.status}</SoftBadge>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {rows.length > 0 ? (
        <ActionCard className="mt-8 !flex-row flex-wrap items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-full bg-teal-bg">
              <ShieldCheck className="h-5 w-5 text-teal" />
            </div>
            <div>
              <h3 className="font-bold text-ink">Human control active</h3>
              <p className="mt-1 max-w-xl text-sm text-text-muted">
                Waypoint will not mark an application submitted without explicit
                submission evidence from you.
              </p>
            </div>
          </div>
          <GoldButton onClick={() => router.push("/approvals")}>
            Open Approvals
          </GoldButton>
        </ActionCard>
      ) : null}
    </AppShell>
  );
}
