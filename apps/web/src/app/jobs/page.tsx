"use client";

import Link from "next/link";
import { FormEvent, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  Bookmark,
  Briefcase,
  Play,
  Sparkles,
  Trash2,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ActionCard } from "@/components/ui/ActionCard";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { Button, GhostButton, GoldButton } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useProcessActivity } from "@/hooks/useProcessActivity";
import { apiFetch } from "@/lib/api";
import { SegmentedTabs } from "@/components/ui/SegmentedTabs";
import { createClient } from "@/lib/supabase/client";
import { useEventStream } from "@/lib/useEventStream";
import { cn } from "@/lib/cn";

type JobMatchSummary = {
  id: string;
  job_id: string;
  status: string;
  score: number | null;
  title: string;
  company_name: string | null;
  location: string | null;
  work_arrangement: string | null;
  url: string | null;
  is_new?: boolean;
  rationale?: string | null;
  application_id?: string | null;
};

const tabs = ["All", "Saved", "New", "High Match", "Applied", "Dismissed"] as const;

const exploreHints = [
  "Staff frontend roles",
  "Fully remote React",
  "Design systems",
  "Product-led teams",
];

function JobsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobMatchSummary[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>("All");
  const [discoveryMode, setDiscoveryMode] = useState<"profile" | "explore">(
    "profile",
  );
  const [exploreQuery, setExploreQuery] = useState("");
  const [activeDiscoveryRunId, setActiveDiscoveryRunId] = useState<string | null>(null);
  const autoDiscoverAttempted = useRef(false);
  const { activeRuns } = useProcessActivity();
  const activeDiscovery = activeRuns.find((run) => run.workflow_type === "job_discovery");
  const discoveryBlocked = Boolean(activeDiscovery || activeDiscoveryRunId);

  const loadJobs = useCallback(async (includeDismissed = false) => {
    const qs = includeDismissed ? "?include_dismissed=true" : "";
    const response = await apiFetch(`/api/v1/jobs${qs}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    return (await response.json()) as JobMatchSummary[];
  }, []);

  const refreshJobs = useCallback(async () => {
    const rows = await loadJobs(activeTab === "Dismissed");
    setJobs(rows);
    setSelected((prev) => {
      const ids = new Set(rows.map((j) => j.id));
      return new Set([...prev].filter((id) => ids.has(id)));
    });
    return rows;
  }, [loadJobs, activeTab]);

  useEventStream({
    onEvent: (event) => {
      if (event.type === "heartbeat") return;
      if (
        event.type === "jobs_discovered" ||
        event.type === "workflow_completed" ||
        event.type === "workflow_cancelled" ||
        event.type === "workflow_failed" ||
        event.type === "workflow_progress"
      ) {
        if (
          event.type === "workflow_completed" ||
          event.type === "workflow_cancelled" ||
          event.type === "workflow_failed"
        ) {
          setActiveDiscoveryRunId(null);
        }
        void refreshJobs().then((rows) => {
          if (event.type === "workflow_completed") {
            if (rows.length === 0) {
              setError(
                "Discovery finished but no jobs were added. Check the activity bar — Firecrawl may be offline.",
              );
              setMessage(null);
            } else {
              setError(null);
              setMessage(
                `Discovery finished. ${rows.length} job${rows.length === 1 ? "" : "s"} ready to review — save top fits or start the pipeline.`,
              );
            }
          }
        });
      }
    },
  });

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
        const rows = await loadJobs(activeTab === "Dismissed");
        if (!cancelled) setJobs(rows);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load jobs");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router, loadJobs, activeTab]);

  useEffect(() => {
    if (autoDiscoverAttempted.current) return;
    if (searchParams.get("discover") !== "1") return;
    if (loading || discoveryBlocked || discovering) return;
    autoDiscoverAttempted.current = true;
    router.replace("/jobs");
    void onDiscover();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-shot handoff from preferences
  }, [searchParams, loading, discoveryBlocked, discovering, router]);

  async function onDiscover(event?: FormEvent) {
    event?.preventDefault();
    if (discoveryBlocked) {
      window.dispatchEvent(new CustomEvent("activity-bar:expand"));
      return;
    }
    setDiscovering(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiFetch("/api/v1/jobs/discover", {
        method: "POST",
        body: JSON.stringify({
          max_results: 5,
          mode: discoveryMode,
          ...(discoveryMode === "explore" && exploreQuery.trim()
            ? { query_hint: exploreQuery.trim() }
            : {}),
        }),
      });
      if (response.status === 409) {
        const body = await response.json().catch(() => null);
        const runId = body?.error?.details?.workflow_run_id as string | undefined;
        if (runId) setActiveDiscoveryRunId(runId);
        window.dispatchEvent(new CustomEvent("activity-bar:expand"));
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      await response.json();
      setMessage("Discovery started — track progress in the activity bar.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start discovery");
    } finally {
      setDiscovering(false);
    }
  }

  async function runBatchAction(
    action: "save" | "dismiss" | "start_pipeline",
    opts?: { force?: boolean },
  ) {
    if (selected.size === 0) return;
    setActing(true);
    setError(null);
    try {
      const response = await apiFetch("/api/v1/jobs/actions/batch", {
        method: "POST",
        body: JSON.stringify({
          match_ids: [...selected],
          action,
          force: Boolean(opts?.force),
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const payload = (await response.json()) as {
        updated?: number;
        started?: number;
        already_running?: number;
        errors?: { match_id?: string; error?: string }[];
        workflows?: { application_id?: string }[];
      };
      setSelected(new Set());
      await refreshJobs();
      const failCount = payload.errors?.length ?? 0;
      const already = payload.already_running ?? 0;
      if (action === "save") {
        setMessage(`Saved ${payload.updated ?? selected.size} job(s).`);
      } else if (action === "dismiss") {
        setMessage(`Removed ${payload.updated ?? selected.size} job(s) from your list.`);
      } else if (failCount > 0 && (payload.started ?? 0) === 0 && already === 0) {
        throw new Error(
          payload.errors?.[0]?.error ||
            `Could not start pipeline for ${failCount} job(s).`,
        );
      } else if (action === "start_pipeline") {
        const started = payload.started ?? 0;
        const appId = payload.workflows?.[0]?.application_id;
        const parts: string[] = [];
        if (started > 0) {
          parts.push(
            `We’re preparing ${started} application${started === 1 ? "" : "s"} — watch progress above. You’ll approve when ready.`,
          );
        }
        if (already > 0) {
          parts.push(
            `${already} already in progress — open Approvals when ready.`,
          );
        }
        if (failCount > 0) {
          parts.push(`${failCount} need attention.`);
        }
        setMessage(parts.join(" ") || "Moved to Applications — watch progress above.");
        if (appId) {
          setActiveTab("Applied");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setActing(false);
    }
  }

  async function singleAction(
    id: string,
    action: "save" | "start_pipeline",
    opts?: { force?: boolean },
  ) {
    setActing(true);
    setError(null);
    try {
      const response = await apiFetch("/api/v1/jobs/actions/batch", {
        method: "POST",
        body: JSON.stringify({
          match_ids: [id],
          action,
          force: Boolean(opts?.force),
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const payload = (await response.json()) as {
        workflows?: { application_id?: string }[];
      };
      await refreshJobs();
      if (action === "start_pipeline") {
        setActiveTab("Applied");
        setMessage(
          "We’re preparing this application — watch progress above. You’ll approve when ready.",
        );
        const appId = payload.workflows?.[0]?.application_id;
        if (appId) {
          // Soft handoff: user can stay on Applied or jump when ready.
        }
      } else {
        setMessage("Saved.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setActing(false);
    }
  }

  function forceReapply(job: JobMatchSummary) {
    const ok = window.confirm(
      `Start a new preparation for “${job.title}”? This re-runs the pipeline for a role you’ve already sent.`,
    );
    if (!ok) return;
    void singleAction(job.id, "start_pipeline", { force: true });
  }

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      if (activeTab === "All")
        return job.status !== "dismissed" && job.status !== "applied";
      if (activeTab === "Dismissed") return job.status === "dismissed";
      if (activeTab === "High Match")
        return (
          job.score != null &&
          job.score >= 0.8 &&
          job.status !== "dismissed" &&
          job.status !== "applied"
        );
      if (activeTab === "Applied") return job.status === "applied";
      if (activeTab === "New") return job.status === "new";
      if (activeTab === "Saved") return job.status === "saved";
      return true;
    });
  }, [jobs, activeTab]);

  return (
    <AppShell active="jobs" wide>
      <PageHeader
        large
        title="Opportunities"
        subtitle="Roles matched to your preferences — review, save, or start an application when you are ready. Nothing is sent without your approval."
        actions={
          <GhostButton onClick={() => router.push("/preferences")}>
            Edit preferences
          </GhostButton>
        }
      />

      <ActionCard highlight className="mb-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-ink">Run discovery</h2>
            <p className="mt-1 max-w-xl text-sm text-text-muted">
              {discoveryMode === "explore"
                ? "Explore widens titles and locations — expect lower precision than profile-matched runs."
                : "Uses your preference targets for higher-precision matches."}
            </p>
          </div>
          <SegmentedTabs
            tabs={[
              { id: "profile", label: "Profile match" },
              { id: "explore", label: "Explore" },
            ]}
            active={discoveryMode}
            onChange={setDiscoveryMode}
          />
        </div>
        <form
          data-discover-form
          onSubmit={(e) => void onDiscover(e)}
          className="mt-5 flex w-full flex-col gap-3 sm:flex-row sm:items-center"
        >
          {discoveryMode === "explore" ? (
            <div className="flex flex-1 items-center gap-2 rounded-2xl border border-line bg-paper px-4 py-2.5 shadow-soft">
              <Sparkles className="h-4 w-4 shrink-0 text-coral" />
              <input
                value={exploreQuery}
                onChange={(e) => setExploreQuery(e.target.value)}
                placeholder="Optional broader craft or title…"
                className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-text-faint"
              />
            </div>
          ) : null}
          <GoldButton
            type="submit"
            disabled={discovering || acting}
            className="w-full sm:w-auto"
          >
            {discoveryBlocked
              ? "Discovery running"
              : discovering
                ? "Starting…"
                : discoveryMode === "explore"
                  ? "Explore with Waypoint"
                  : "Find profile matches"}
            <ArrowRight className="ml-1 h-3.5 w-3.5" />
          </GoldButton>
        </form>
        {discoveryMode === "explore" ? (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-text-faint">Try exploring</span>
            {exploreHints.map((hint) => (
              <button
                key={hint}
                type="button"
                onClick={() => setExploreQuery(hint)}
                className="rounded-full border border-line bg-white px-3 py-1 text-xs font-medium text-text-muted hover:border-coral/40 hover:text-ink"
              >
                {hint}
              </button>
            ))}
          </div>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-4 border-t border-line pt-4 text-sm font-semibold text-coral">
          <Link href="/preferences" className="hover:underline">
            Set preferences
          </Link>
          <Link href="/approvals" className="hover:underline">
            Review approvals
          </Link>
          <Link href="/applications" className="hover:underline">
            View applications
          </Link>
        </div>
      </ActionCard>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold tracking-tight text-ink">
          Your list
          <span className="ml-2 text-base font-semibold text-text-muted">
            ({filteredJobs.length})
          </span>
        </h2>
        <SegmentedTabs
          tabs={tabs.map((t) => ({ id: t, label: t }))}
          active={activeTab}
          onChange={setActiveTab}
          variant="underline"
        />
      </div>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {message ? (
        <div className="mb-4 flex flex-wrap items-center gap-3 text-sm text-coral">
          <p>{message}</p>
          {message.toLowerCase().includes("preparing") ||
          message.toLowerCase().includes("approvals") ? (
            <Link href="/approvals" className="font-semibold underline">
              Go to Approvals
            </Link>
          ) : null}
        </div>
      ) : null}

      {selected.size > 0 ? (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-white px-4 py-3 shadow-soft">
          <span className="text-sm text-ink">{selected.size} selected</span>
          {activeTab !== "Applied" ? (
            <>
              <Button
                variant="secondary"
                disabled={acting}
                className="!rounded-full px-3 py-1.5 text-xs"
                onClick={() => void runBatchAction("save")}
              >
                <Bookmark className="mr-1.5 h-3.5 w-3.5" />
                Save
              </Button>
              <Button
                disabled={acting}
                className="!rounded-full px-3 py-1.5 text-xs"
                onClick={() => void runBatchAction("start_pipeline")}
              >
                <Play className="mr-1.5 h-3.5 w-3.5" />
                Start pipeline
              </Button>
            </>
          ) : null}
          <Button
            variant="secondary"
            disabled={acting}
            className="!rounded-full px-3 py-1.5 text-xs"
            onClick={() => void runBatchAction("dismiss")}
          >
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Remove
          </Button>
        </div>
      ) : null}

      {loading ? (
        <p className="py-8 text-sm text-text-muted">Loading…</p>
      ) : filteredJobs.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No opportunities yet"
          description="Set your preferences first, then run discovery above to surface matching roles."
          primaryActionLabel="Set preferences"
          actionHref="/preferences"
        />
      ) : (
        <ul className="space-y-4">
          {filteredJobs.map((job) => {
            const scorePct =
              job.score != null ? Math.round(job.score * 100) : null;
            const initial = (job.company_name || job.title || "?").charAt(0);
            return (
              <li key={job.id}>
                <ActionCard className="!rounded-2xl !p-5 shadow-card sm:!p-6">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="flex min-w-0 flex-1 gap-3">
                      <input
                        type="checkbox"
                        checked={selected.has(job.id)}
                        onChange={() => {
                          setSelected((prev) => {
                            const next = new Set(prev);
                            if (next.has(job.id)) next.delete(job.id);
                            else next.add(job.id);
                            return next;
                          });
                        }}
                        className="mt-2 h-4 w-4 rounded border-line"
                        aria-label={`Select ${job.title}`}
                      />
                      <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-lavender text-sm font-bold text-lavender-deep">
                        {initial}
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            href={`/jobs/${job.id}`}
                            className="text-lg font-bold text-ink hover:text-coral"
                          >
                            {job.title}
                          </Link>
                          {job.is_new ? (
                            <SoftBadge tone="coral">New</SoftBadge>
                          ) : null}
                          {scorePct != null ? (
                            <SoftBadge
                              tone={scorePct >= 80 ? "mint" : "lavender"}
                            >
                              {scorePct}% alignment
                            </SoftBadge>
                          ) : null}
                        </div>
                        <p className="mt-1 text-sm text-text-muted">
                          {[job.company_name, job.location, job.work_arrangement]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                        <div
                          className={cn(
                            "mt-3 rounded-2xl px-3 py-2.5 text-sm text-ink",
                            "bg-coral-bg/60",
                          )}
                        >
                          <p className="text-[10px] font-bold uppercase tracking-wider text-coral-deep">
                            Why this may fit
                          </p>
                          <p className="mt-1 text-text-muted">
                            {job.rationale?.trim() ||
                              `Match status: ${job.status}. Open the role to review details before starting a pitch.`}
                          </p>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <SoftBadge
                            tone={job.status === "applied" ? "mint" : "white"}
                          >
                            {job.status === "applied" ? "Applied" : job.status}
                          </SoftBadge>
                        </div>
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2 sm:flex-col sm:items-stretch">
                      {job.status === "applied" ? (
                        <>
                          {job.application_id ? (
                            <GoldButton
                              onClick={() =>
                                router.push(`/applications/${job.application_id}`)
                              }
                            >
                              View application
                            </GoldButton>
                          ) : (
                            <GoldButton onClick={() => router.push("/applications")}>
                              Open applications
                            </GoldButton>
                          )}
                          <GhostButton
                            disabled={acting}
                            onClick={() => forceReapply(job)}
                          >
                            Re-prepare (force)
                          </GhostButton>
                          <Link
                            href={`/jobs/${job.id}`}
                            className="text-center text-xs font-semibold text-coral"
                          >
                            Review dossier →
                          </Link>
                        </>
                      ) : (
                        <>
                          <GoldButton
                            disabled={acting}
                            onClick={() => void singleAction(job.id, "start_pipeline")}
                          >
                            Start tailored pitch
                          </GoldButton>
                          <GhostButton
                            disabled={acting}
                            onClick={() => void singleAction(job.id, "save")}
                          >
                            Save for later
                          </GhostButton>
                          <Link
                            href={`/jobs/${job.id}`}
                            className="text-center text-xs font-semibold text-coral"
                          >
                            Review dossier →
                          </Link>
                        </>
                      )}
                    </div>
                  </div>
                </ActionCard>
              </li>
            );
          })}
        </ul>
      )}
    </AppShell>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={<AppShell active="jobs" wide><p className="text-sm text-text-muted">Loading…</p></AppShell>}>
      <JobsPageInner />
    </Suspense>
  );
}
