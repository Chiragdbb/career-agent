"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
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
    <AppShell active="jobs" wide>
      <Link href="/jobs" className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground">
        ← Back to jobs
      </Link>
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {job ? (
        <article className="space-y-6">
          <header className="space-y-2">
            <h1 className="font-serif text-2xl text-foreground">{job.title}</h1>
            <p className="text-sm text-muted-foreground">
              {[job.company_name, job.location, job.work_arrangement]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <Badge variant="primary">
                Match: {job.score != null ? `${Math.round(job.score * 100)}%` : "—"}
              </Badge>
              <Badge variant="default">{job.status}</Badge>
              {job.url ? (
                <a
                  href={job.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary hover:underline"
                >
                  View posting
                </a>
              ) : null}
              <Button
                variant="secondary"
                onClick={() => void onRescore()}
                disabled={rescoring}
              >
                {rescoring ? "Re-scoring…" : "Re-score"}
              </Button>
            </div>
          </header>

          {job.explanation ? (
            <Card>
              <CardTitle>Why it matches</CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">{job.explanation}</p>
            </Card>
          ) : null}

          <section className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardTitle className="text-success">Matched skills</CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">
                {job.matched_skills.join(", ") || "None"}
              </p>
            </Card>
            <Card>
              <CardTitle className="text-warning">Missing requirements</CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">
                {job.missing_skills.join(", ") || "None"}
              </p>
            </Card>
          </section>

          <Card>
            <CardTitle>Company research</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              {workspace?.company_research?.summary || "Not researched yet"}
            </p>
          </Card>

          <Card>
            <CardTitle>People / contacts</CardTitle>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {(workspace?.contacts || []).map((c, idx) => (
                <li key={`${c.name}-${idx}`}>
                  {c.name || "Unknown"} · {c.status}
                  {c.email_verifications?.length
                    ? ` · ${c.email_verifications.map((v) => `${v.email} (${v.status})`).join(", ")}`
                    : ""}
                </li>
              ))}
              {!workspace?.contacts?.length ? (
                <li className="text-muted-foreground">No contacts yet</li>
              ) : null}
            </ul>
          </Card>

          <Card>
            <CardTitle>Strategy</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              {workspace?.strategy?.summary || "—"}
            </p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {(workspace?.strategy?.recommended_actions || []).map((a) => (
                <li key={`${a.action}-${a.priority}`}>
                  {a.priority}. {a.action}
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <CardTitle>Application / documents / outreach</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              Application:{" "}
              {workspace?.application
                ? `${workspace.application.status} (${workspace.application.id})`
                : "None"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Documents:{" "}
              {(workspace?.documents || [])
                .map((d) => d.filename || d.id)
                .join(", ") || "None"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Outreach:{" "}
              {(workspace?.outreach || [])
                .map((o) => `${o.subject || o.id} (${o.status})`)
                .join(", ") || "None"}
            </p>
          </Card>

          <Card>
            <CardTitle>Timeline</CardTitle>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {(workspace?.timeline || []).map((e, idx) => (
                <li key={`${e.event_type}-${idx}`}>
                  {e.event_type}
                  {e.created_at ? ` · ${e.created_at}` : ""}
                </li>
              ))}
              {!workspace?.timeline?.length ? (
                <li className="text-muted-foreground">No events yet</li>
              ) : null}
            </ul>
          </Card>
        </article>
      ) : null}
    </AppShell>
  );
}
