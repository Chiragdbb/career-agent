"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type ScoreBreakdown = {
  total: number;
  role: number;
  location: number;
  work_arrangement: number;
  salary: number;
  skills: number;
  seniority: number;
  notes: string[];
};

type JobMatchDetail = {
  id: string;
  job_id: string;
  status: string;
  score: number | null;
  title: string;
  company_name: string | null;
  location: string | null;
  work_arrangement: string | null;
  url: string | null;
  description: string | null;
  job_skills: string[];
  matched_skills: string[];
  missing_skills: string[];
  score_breakdown: ScoreBreakdown | null;
  explanation: string | null;
};

export default function JobDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const matchId = params.id;

  const [loading, setLoading] = useState(true);
  const [rescoring, setRescoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobMatchDetail | null>(null);

  async function fetchJob(rescore = false) {
    const path = rescore
      ? `/api/v1/jobs/${matchId}/score`
      : `/api/v1/jobs/${matchId}`;
    const response = await apiFetch(path, rescore ? { method: "POST" } : {});
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    return (await response.json()) as JobMatchDetail;
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
        const detail = await fetchJob(false);
        if (!cancelled) setJob(detail);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load job");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId, router]);

  async function onRescore() {
    setRescoring(true);
    setError(null);
    try {
      const detail = await fetchJob(true);
      setJob(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to re-score job");
    } finally {
      setRescoring(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <AppNav active="jobs" />

      <Link href="/jobs" className="text-sm text-zinc-600 hover:text-zinc-900">
        ← Back to jobs
      </Link>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {loading ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : job ? (
        <article className="space-y-6">
          <header className="space-y-2">
            <h1 className="text-2xl font-semibold text-zinc-900">{job.title}</h1>
            <p className="text-sm text-zinc-600">
              {[job.company_name, job.location, job.work_arrangement]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span className="font-medium text-zinc-900">
                Match score:{" "}
                {job.score != null ? `${Math.round(job.score * 100)}%` : "—"}
              </span>
              <span className="text-zinc-500">Status: {job.status}</span>
              {job.url ? (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-700 hover:underline"
                >
                  View posting
                </a>
              ) : null}
              <button
                type="button"
                onClick={() => void onRescore()}
                disabled={rescoring}
                className="rounded border border-zinc-300 px-3 py-1 text-sm disabled:opacity-60"
              >
                {rescoring ? "Re-scoring…" : "Re-score"}
              </button>
            </div>
          </header>

          {job.explanation ? (
            <section>
              <h2 className="text-sm font-medium text-zinc-800">Match explanation</h2>
              <p className="mt-2 text-sm text-zinc-700">{job.explanation}</p>
            </section>
          ) : null}

          <section className="grid gap-4 sm:grid-cols-2">
            <div>
              <h2 className="text-sm font-medium text-green-800">Matched skills</h2>
              {job.matched_skills.length ? (
                <ul className="mt-2 flex flex-wrap gap-2 text-sm">
                  {job.matched_skills.map((skill) => (
                    <li
                      key={skill}
                      className="rounded bg-green-50 px-2 py-1 text-green-900"
                    >
                      {skill}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-zinc-500">None identified</p>
              )}
            </div>
            <div>
              <h2 className="text-sm font-medium text-amber-800">Missing skills</h2>
              {job.missing_skills.length ? (
                <ul className="mt-2 flex flex-wrap gap-2 text-sm">
                  {job.missing_skills.map((skill) => (
                    <li
                      key={skill}
                      className="rounded bg-amber-50 px-2 py-1 text-amber-900"
                    >
                      {skill}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-zinc-500">None identified</p>
              )}
            </div>
          </section>

          {job.score_breakdown ? (
            <section>
              <h2 className="text-sm font-medium text-zinc-800">Score breakdown</h2>
              <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                {(
                  [
                    ["Role", job.score_breakdown.role],
                    ["Location", job.score_breakdown.location],
                    ["Work arrangement", job.score_breakdown.work_arrangement],
                    ["Salary", job.score_breakdown.salary],
                    ["Skills", job.score_breakdown.skills],
                    ["Seniority", job.score_breakdown.seniority],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-zinc-500">{label}</dt>
                    <dd className="font-medium text-zinc-900">
                      {Math.round(value * 100)}%
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}

          {job.description ? (
            <section>
              <h2 className="text-sm font-medium text-zinc-800">Description</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-700">
                {job.description}
              </p>
            </section>
          ) : null}
        </article>
      ) : null}
    </main>
  );
}
