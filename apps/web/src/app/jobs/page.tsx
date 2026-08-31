"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { apiFetch } from "@/lib/api";
import { SegmentedTabs } from "@/components/ui/SegmentedTabs";
import { createClient } from "@/lib/supabase/client";

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
};

const tabs = ["All", "Saved", "New", "High Match", "Applied"] as const;

export default function JobsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobMatchSummary[]>([]);
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>("All");

  async function loadJobs() {
    const response = await apiFetch("/api/v1/jobs");
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    return (await response.json()) as JobMatchSummary[];
  }

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
        const rows = await loadJobs();
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
  }, [router]);

  async function onDiscover(event: FormEvent) {
    event.preventDefault();
    setDiscovering(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiFetch("/api/v1/jobs/discover", {
        method: "POST",
        body: JSON.stringify({ max_results: 5 }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const payload = (await response.json()) as {
        workflow_run_id: string;
        status: string;
      };
      setMessage(
        `Discovery queued (${payload.status}). Refresh in a moment to see new matches.`,
      );
      const rows = await loadJobs();
      setJobs(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start discovery");
    } finally {
      setDiscovering(false);
    }
  }

  const filteredJobs = jobs.filter((job) => {
    if (activeTab === "All") return true;
    if (activeTab === "High Match") return job.score != null && job.score >= 0.8;
    if (activeTab === "Applied") return job.status.toLowerCase().includes("applied");
    if (activeTab === "New") return job.status.toLowerCase().includes("new");
    if (activeTab === "Saved") return job.status.toLowerCase().includes("saved");
    return true;
  });

  return (
    <AppShell active="jobs" wide>
      <PageHeader
        title="Jobs"
        actions={
          <form onSubmit={(e) => void onDiscover(e)} className="w-full sm:w-auto">
            <Button type="submit" disabled={discovering} className="w-full sm:w-auto">
              {discovering ? "Queueing…" : "Discover More"}
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

      {loading ? (
        <p className="py-8 text-sm text-muted-foreground">Loading…</p>
      ) : filteredJobs.length === 0 ? (
        <p className="py-8 text-sm text-muted-foreground">
          No jobs yet. Set preferences and run discovery.
        </p>
      ) : (
        <>
          <ul className="space-y-2 md:hidden">
            {filteredJobs.map((job) => (
              <li key={job.id}>
                <Link
                  href={`/jobs/${job.id}`}
                  className="block rounded-lg border border-border bg-card p-4 transition-colors hover:bg-muted/30"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-foreground">{job.title}</p>
                    <span className="shrink-0 text-xs font-semibold text-primary">
                      {job.score != null ? `${Math.round(job.score * 100)}%` : "—"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {[job.company_name, job.location, job.work_arrangement]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  <Badge variant="default" className="mt-2 capitalize">
                    {job.status}
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-hidden rounded-lg border border-border bg-card md:block">
            <div className="grid grid-cols-[1fr_120px_100px_80px] gap-4 border-b border-border bg-muted px-4 py-3 text-xs text-muted-foreground">
              <span>Job</span>
              <span>Location</span>
              <span>Match</span>
              <span>Status</span>
            </div>
            <ul>
              {filteredJobs.map((job) => (
                <li
                  key={job.id}
                  className="grid grid-cols-[1fr_120px_100px_80px] gap-4 border-b border-border px-4 py-3.5 last:border-0 hover:bg-muted/30"
                >
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
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </AppShell>
  );
}
