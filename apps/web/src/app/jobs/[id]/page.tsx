"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Workspace = {
  match: {
    id: string;
    title: string;
    company_name: string | null;
    location: string | null;
    work_arrangement: string | null;
    score: number | null;
    status: string;
    url: string | null;
    explanation: string | null;
    matched_skills: string[];
    missing_skills: string[];
    description: string | null;
    score_breakdown: {
      role: number;
      location: number;
      work_arrangement: number;
      salary: number;
      skills: number;
      seniority: number;
    } | null;
  };
  company_research: { summary: string | null; status: string } | null;
  people: { name: string | null; title: string | null; status: string }[];
  contacts: { name: string | null; status: string; email_verifications: { email: string; status: string }[] }[];
  strategy: { summary: string; recommended_actions: { action: string; priority: number }[] } | null;
  application: { id: string; status: string } | null;
  outreach: { id: string; subject: string | null; status: string }[];
  documents: { id: string; filename: string | null; status: string }[];
  timeline: { event_type: string; created_at?: string }[];
};

export default function JobDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const matchId = params.id;

  const [loading, setLoading] = useState(true);
  const [rescoring, setRescoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);

  async function fetchWorkspace() {
    const response = await apiFetch(`/api/v1/jobs/${matchId}/workspace`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    return (await response.json()) as Workspace;
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
        const detail = await fetchWorkspace();
        if (!cancelled) setWorkspace(detail);
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
      const response = await apiFetch(`/api/v1/jobs/${matchId}/score`, {
        method: "POST",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setWorkspace(await fetchWorkspace());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to re-score job");
    } finally {
      setRescoring(false);
    }
  }

  const job = workspace?.match;

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <AppNav active="jobs" />
      <Link href="/jobs" className="text-sm text-zinc-600 hover:text-zinc-900">
        ← Back to jobs
      </Link>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {loading ? <p className="text-sm text-zinc-500">Loading…</p> : null}
      {job ? (
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
            <section className="rounded border border-zinc-200 p-4">
              <h2 className="text-sm font-medium text-zinc-800">Why it matches</h2>
              <p className="mt-2 text-sm text-zinc-700">{job.explanation}</p>
            </section>
          ) : null}

          <section className="grid gap-4 sm:grid-cols-2">
            <div className="rounded border border-zinc-200 p-4">
              <h2 className="text-sm font-medium text-green-800">Matched skills</h2>
              <p className="mt-2 text-sm text-zinc-700">
                {job.matched_skills.join(", ") || "None"}
              </p>
            </div>
            <div className="rounded border border-zinc-200 p-4">
              <h2 className="text-sm font-medium text-amber-800">
                Missing requirements
              </h2>
              <p className="mt-2 text-sm text-zinc-700">
                {job.missing_skills.join(", ") || "None"}
              </p>
            </div>
          </section>

          <section className="rounded border border-zinc-200 p-4">
            <h2 className="text-sm font-medium text-zinc-800">Company research</h2>
            <p className="mt-2 text-sm text-zinc-700">
              {workspace?.company_research?.summary || "Not researched yet"}
            </p>
          </section>

          <section className="rounded border border-zinc-200 p-4">
            <h2 className="text-sm font-medium text-zinc-800">People / contacts</h2>
            <ul className="mt-2 space-y-1 text-sm text-zinc-700">
              {(workspace?.contacts || []).map((c, idx) => (
                <li key={`${c.name}-${idx}`}>
                  {c.name || "Unknown"} · {c.status}
                  {c.email_verifications?.length
                    ? ` · ${c.email_verifications.map((v) => `${v.email} (${v.status})`).join(", ")}`
                    : ""}
                </li>
              ))}
              {!workspace?.contacts?.length ? (
                <li className="text-zinc-500">No contacts yet</li>
              ) : null}
            </ul>
          </section>

          <section className="rounded border border-zinc-200 p-4">
            <h2 className="text-sm font-medium text-zinc-800">Strategy</h2>
            <p className="mt-2 text-sm text-zinc-700">
              {workspace?.strategy?.summary || "—"}
            </p>
            <ul className="mt-2 space-y-1 text-sm text-zinc-600">
              {(workspace?.strategy?.recommended_actions || []).map((a) => (
                <li key={`${a.action}-${a.priority}`}>
                  {a.priority}. {a.action}
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded border border-zinc-200 p-4">
            <h2 className="text-sm font-medium text-zinc-800">
              Application / documents / outreach
            </h2>
            <p className="mt-2 text-sm text-zinc-700">
              Application:{" "}
              {workspace?.application
                ? `${workspace.application.status} (${workspace.application.id})`
                : "None"}
            </p>
            <p className="mt-1 text-sm text-zinc-700">
              Documents:{" "}
              {(workspace?.documents || [])
                .map((d) => d.filename || d.id)
                .join(", ") || "None"}
            </p>
            <p className="mt-1 text-sm text-zinc-700">
              Outreach:{" "}
              {(workspace?.outreach || [])
                .map((o) => `${o.subject || o.id} (${o.status})`)
                .join(", ") || "None"}
            </p>
          </section>

          <section className="rounded border border-zinc-200 p-4">
            <h2 className="text-sm font-medium text-zinc-800">Timeline</h2>
            <ul className="mt-2 space-y-1 text-sm text-zinc-700">
              {(workspace?.timeline || []).map((e, idx) => (
                <li key={`${e.event_type}-${idx}`}>
                  {e.event_type}
                  {e.created_at ? ` · ${e.created_at}` : ""}
                </li>
              ))}
              {!workspace?.timeline?.length ? (
                <li className="text-zinc-500">No events yet</li>
              ) : null}
            </ul>
          </section>
        </article>
      ) : null}
    </main>
  );
}
