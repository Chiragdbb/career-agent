"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
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

export default function JobsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobMatchSummary[]>([]);

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

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <AppNav active="jobs" />

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900">Discovered Jobs</h1>
          <p className="mt-2 text-sm text-zinc-600">
            Jobs matched to your preferences with deterministic scores.
          </p>
        </div>
        <form onSubmit={(e) => void onDiscover(e)}>
          <button
            type="submit"
            disabled={discovering}
            className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {discovering ? "Queueing…" : "Discover jobs"}
          </button>
        </form>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {message ? <p className="text-sm text-green-700">{message}</p> : null}

      {loading ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : jobs.length === 0 ? (
        <p className="text-sm text-zinc-500">
          No jobs yet. Set preferences and run discovery.
        </p>
      ) : (
        <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
          {jobs.map((job) => (
            <li key={job.id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <Link
                    href={`/jobs/${job.id}`}
                    className="font-medium text-zinc-900 hover:underline"
                  >
                    {job.title}
                  </Link>
                  <p className="mt-1 text-sm text-zinc-600">
                    {[job.company_name, job.location, job.work_arrangement]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <div className="text-right text-sm">
                  <p className="font-medium text-zinc-900">
                    {job.score != null ? `${Math.round(job.score * 100)}%` : "—"}
                  </p>
                  <p className="text-zinc-500">{job.status}</p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
