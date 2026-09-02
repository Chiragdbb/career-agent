"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Bookmark, Briefcase, ExternalLink, Play, Trash2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
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
};

const tabs = ["All", "Saved", "New", "High Match", "Applied", "Dismissed"] as const;

export default function JobsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobMatchSummary[]>([]);
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>("All");
  const [activeDiscoveryRunId, setActiveDiscoveryRunId] = useState<string | null>(null);
  const { activeRuns } = useProcessActivity();
  const activeDiscovery = activeRuns.find((run) => run.workflow_type === "job_discovery");
  const discoveryBlocked = Boolean(activeDiscoveryRunId || activeDiscovery);

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
        event.type === "workflow_progress"
      ) {
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
                `Discovery finished. ${rows.length} job${rows.length === 1 ? "" : "s"} ready to review.`,
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

  async function onDiscover(event: FormEvent) {
    event.preventDefault();
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
        body: JSON.stringify({ max_results: 5 }),
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

  async function runBatchAction(action: "save" | "dismiss" | "start_pipeline") {
    if (selected.size === 0) return;
    setActing(true);
    setError(null);
    try {
      const response = await apiFetch("/api/v1/jobs/actions/batch", {
        method: "POST",
        body: JSON.stringify({
          match_ids: [...selected],
          action,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const payload = (await response.json()) as { updated?: number; started?: number };
      setSelected(new Set());
      await refreshJobs();
      if (action === "save") {
        setMessage(`Saved ${payload.updated ?? selected.size} job(s).`);
      } else if (action === "dismiss") {
        setMessage(`Removed ${payload.updated ?? selected.size} job(s) from your list.`);
      } else {
        setMessage(`Started pipeline for ${payload.started ?? selected.size} job(s).`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setActing(false);
    }
  }

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      if (activeTab === "All") return job.status !== "dismissed";
      if (activeTab === "Dismissed") return job.status === "dismissed";
      if (activeTab === "High Match") return job.score != null && job.score >= 0.8;
      if (activeTab === "Applied") return job.status.toLowerCase().includes("applied");
      if (activeTab === "New") return job.status === "new";
      if (activeTab === "Saved") return job.status === "saved";
      return true;
    });
  }, [jobs, activeTab]);

  const allSelected =
    filteredJobs.length > 0 && filteredJobs.every((j) => selected.has(j.id));

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filteredJobs.map((j) => j.id)));
    }
  }

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <AppShell active="jobs" wide>
      <PageHeader
        title="Jobs"
        actions={
          <form
            data-discover-form
            onSubmit={(e) => void onDiscover(e)}
            className="w-full sm:w-auto"
          >
            <Button
              type="submit"
              disabled={discovering || acting}
              title={discoveryBlocked ? "Discovery already running" : undefined}
              className="w-full sm:w-auto"
            >
              {discoveryBlocked
                ? "Discovery already running"
                : discovering
                  ? "Starting…"
                  : "Discover More"}
            </Button>
          </form>
        }
      />

      <SegmentedTabs
        tabs={tabs.map((t) => ({ id: t, label: t }))}
        active={activeTab}
        onChange={setActiveTab}
        variant="underline"
        className="mb-4"
      />

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {message ? <p className="mb-4 text-sm text-primary">{message}</p> : null}

      {selected.size > 0 ? (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/30 px-4 py-3">
          <span className="text-sm text-foreground">{selected.size} selected</span>
          <Button
            variant="secondary"
            disabled={acting}
            className="px-3 py-1.5 text-xs"
            onClick={() => void runBatchAction("save")}
          >
            <Bookmark className="mr-1.5 h-3.5 w-3.5" />
            Save
          </Button>
          <Button
            disabled={acting}
            className="px-3 py-1.5 text-xs"
            onClick={() => void runBatchAction("start_pipeline")}
          >
            <Play className="mr-1.5 h-3.5 w-3.5" />
            Start pipeline
          </Button>
          <Button
            variant="secondary"
            disabled={acting}
            className="px-3 py-1.5 text-xs"
            onClick={() => void runBatchAction("dismiss")}
          >
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Remove
          </Button>
        </div>
      ) : null}

      {loading ? (
        <p className="py-8 text-sm text-muted-foreground">Loading…</p>
      ) : filteredJobs.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No jobs yet"
          description="Set your preferences and run discovery to find matching roles."
          primaryActionLabel="Discover jobs"
          onPrimaryAction={() => {
            const form = document.querySelector<HTMLFormElement>("form[data-discover-form]");
            form?.requestSubmit();
          }}
        />
      ) : (
        <>
          <ul className="space-y-2 md:hidden">
            {filteredJobs.map((job) => (
              <li
                key={job.id}
                className={cn(
                  "rounded-lg border border-border bg-card p-4",
                  selected.has(job.id) && "ring-2 ring-primary/30",
                )}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selected.has(job.id)}
                    onChange={() => toggleOne(job.id)}
                    className="mt-1 h-4 w-4 rounded border-border"
                    aria-label={`Select ${job.title}`}
                  />
                  <div className="min-w-0 flex-1">
                    <Link href={`/jobs/${job.id}`} className="font-medium text-foreground hover:text-primary">
                      {job.title}
                    </Link>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {[job.company_name, job.location, job.work_arrangement]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                    <div className="mt-2 flex items-center gap-2">
                      {job.is_new ? (
                        <Badge variant="primary" className="text-[10px]">
                          New
                        </Badge>
                      ) : null}
                      <Badge variant="default" className="capitalize">
                        {job.status}
                      </Badge>
                      <span className="text-xs font-semibold text-primary">
                        {job.score != null ? `${Math.round(job.score * 100)}%` : "—"}
                      </span>
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-hidden rounded-lg border border-border bg-card md:block">
            <div className="grid grid-cols-[40px_1fr_120px_100px_100px_120px] gap-4 border-b border-border bg-muted px-4 py-3 text-xs text-muted-foreground">
              <span>
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  aria-label="Select all jobs"
                  className="h-4 w-4 rounded border-border"
                />
              </span>
              <span>Job</span>
              <span>Location</span>
              <span>Match</span>
              <span>Status</span>
              <span>Actions</span>
            </div>
            <ul>
              {filteredJobs.map((job) => (
                <li
                  key={job.id}
                  className={cn(
                    "grid grid-cols-[40px_1fr_120px_100px_100px_120px] gap-4 border-b border-border px-4 py-3.5 last:border-0 hover:bg-muted/30",
                    selected.has(job.id) && "bg-primary/5",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(job.id)}
                    onChange={() => toggleOne(job.id)}
                    className="mt-1 h-4 w-4 rounded border-border"
                    aria-label={`Select ${job.title}`}
                  />
                  <div>
                    <Link
                      href={`/jobs/${job.id}`}
                      className="text-sm font-medium text-foreground hover:text-primary"
                    >
                      {job.title}
                    </Link>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {job.company_name}
                      {job.work_arrangement ? ` · ${job.work_arrangement}` : ""}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {job.location || "—"}
                  </span>
                  <span className="text-xs font-semibold text-primary">
                    {job.score != null ? `${Math.round(job.score * 100)}%` : "—"}
                  </span>
                  <Badge variant="default" className="w-fit capitalize">
                    {job.status}
                  </Badge>
                  <div className="flex items-center gap-1">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="View details"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </AppShell>
  );
}
