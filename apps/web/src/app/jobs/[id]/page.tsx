"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  MapPin,
  Send,
  Sparkles,
  Star,
  Target,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { GoldButton, GhostButton } from "@/components/ui/Button";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ScoreRing } from "@/components/ui/ScoreRing";
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
  };
  contacts: {
    id: string;
    name: string | null;
    title: string | null;
    status: string;
    email_verifications: { email: string; status: string }[];
  }[];
  application: { id: string; status: string } | null;
  outreach: { id: string; contact_id: string; subject: string | null; status: string }[];
};

export default function JobDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const matchId = params.id;

  const [loading, setLoading] = useState(true);
  const [rescoring, setRescoring] = useState(false);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<"save" | "start" | null>(null);
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
        if (!cancelled) {
          setWorkspace(detail);
          setSaved(detail.match.status === "saved");
        }
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

  async function onSaveJob() {
    setActionError(null);
    setLastAction("save");
    setSaving(true);
    try {
      const response = await apiFetch(`/api/v1/jobs/${matchId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "saved" }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setSaved(true);
      setWorkspace(await fetchWorkspace());
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to save job");
    } finally {
      setSaving(false);
    }
  }

  async function onStartApplication() {
    setActionError(null);
    setLastAction("start");
    setStarting(true);
    try {
      const response = await apiFetch("/api/v1/jobs/actions/batch", {
        method: "POST",
        body: JSON.stringify({
          match_ids: [matchId],
          action: "start_pipeline",
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const refreshed = await fetchWorkspace();
      setWorkspace(refreshed);
      const targetId = refreshed.application?.id;
      if (targetId) router.push(`/applications/${targetId}`);
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Failed to start application",
      );
    } finally {
      setStarting(false);
    }
  }

  function retryAction() {
    if (lastAction === "save") void onSaveJob();
    else if (lastAction === "start") void onStartApplication();
  }

  function outreachHref(contactId: string): string {
    const existing = workspace?.outreach.find((o) => o.contact_id === contactId);
    return existing ? `/outreach/${existing.id}` : `/contacts/${contactId}`;
  }

  const job = workspace?.match;
  const hasApplication = Boolean(workspace?.application);
  const scorePercent = job?.score != null ? Math.round(job.score * 100) : null;

  return (
    <AppShell active="jobs" wide>
      <Link
        href="/jobs"
        className="mb-3.5 inline-flex items-center gap-1.5 text-[12.5px] text-text-muted hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to jobs
      </Link>
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {actionError ? (
        <ErrorBanner message={actionError} onRetry={retryAction} />
      ) : null}
      {loading ? <p className="text-sm text-text-muted">Loading…</p> : null}
      {job ? (
        <article className="max-w-[760px]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="font-serif text-2xl font-semibold text-ink">{job.title}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-3.5">
                {job.company_name ? (
                  <span className="flex items-center gap-1.5 text-[13.5px] text-text-muted">
                    <Building2 className="h-3.5 w-3.5" /> {job.company_name}
                  </span>
                ) : null}
                {(job.location || job.work_arrangement) ? (
                  <span className="flex items-center gap-1.5 text-[13.5px] text-text-muted">
                    <MapPin className="h-3.5 w-3.5" />
                    {[job.work_arrangement, job.location].filter(Boolean).join(" · ")}
                  </span>
                ) : null}
              </div>
            </div>
            {scorePercent != null ? <ScoreRing value={scorePercent} /> : null}
          </div>

          <div className="mb-6 mt-5 flex min-h-[38px] flex-wrap items-center gap-2.5">
            {hasApplication ? (
              <GhostButton
                icon={ArrowRight}
                className="border-teal bg-teal-bg text-teal"
                onClick={() =>
                  router.push(`/applications/${workspace!.application!.id}`)
                }
              >
                View application
              </GhostButton>
            ) : (
              <>
                <GhostButton
                  icon={Star}
                  disabled={saving || starting}
                  onClick={() => void onSaveJob()}
                  className={
                    saved ? "border-gold bg-gold-bg text-[#7A551D]" : undefined
                  }
                >
                  {saving ? "Saving…" : saved ? "Saved" : "Save job"}
                </GhostButton>
                <GoldButton
                  icon={Sparkles}
                  loading={starting}
                  disabled={saving || starting}
                  onClick={() => void onStartApplication()}
                >
                  {starting ? "Preparing application" : "Start application"}
                </GoldButton>
              </>
            )}
            <span className="ml-1 flex gap-3 text-xs text-text-faint">
              {job.url ? (
                <a href={job.url} target="_blank" rel="noreferrer" className="hover:text-foreground">
                  View posting
                </a>
              ) : null}
              <button
                type="button"
                onClick={() => void onRescore()}
                disabled={rescoring}
                className="hover:text-foreground"
              >
                {rescoring ? "Re-scoring…" : "Re-score"}
              </button>
            </span>
          </div>

          {job.explanation ? (
            <div className="mb-4 rounded-xl bg-teal-bg px-[18px] py-4">
              <div className="mb-1.5 flex items-center gap-1.5">
                <Target className="h-3.5 w-3.5 text-teal" />
                <span className="text-[12.5px] font-semibold text-teal">Why it matches</span>
              </div>
              <p className="text-[13.5px] leading-relaxed text-[#254E42]">{job.explanation}</p>
            </div>
          ) : null}

          <div className="mb-5 flex flex-col gap-2.5">
            <CollapsibleSection
              title={`Matched skills (${job.matched_skills.length})`}
              tone="good"
              defaultOpen
              chips={job.matched_skills.length ? job.matched_skills : ["None listed"]}
            />
            <CollapsibleSection
              title={`Missing requirements (${job.missing_skills.length})`}
              tone="warn"
              defaultOpen={false}
              chips={job.missing_skills.length ? job.missing_skills : ["None identified"]}
            />
          </div>

          {(workspace?.contacts?.length ?? 0) > 0 ? (
            <section>
              <h2 className="mb-2.5 font-serif text-[15.5px] font-semibold text-ink">
                People at {job.company_name || "this company"}
              </h2>
              <div className="flex flex-col gap-2">
                {workspace!.contacts.map((c) => {
                  const initials = (c.name || "?")
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase();
                  const verified = c.email_verifications?.some(
                    (v) => v.status === "verified",
                  );
                  return (
                    <div
                      key={c.id}
                      className="flex items-center gap-3 rounded-[10px] border border-line-soft bg-paper-raised px-3.5 py-2.5"
                    >
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gold-bg font-serif text-xs font-semibold text-[#7A551D]">
                        {initials}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-[13.5px] font-medium text-ink">{c.name}</p>
                        <p className="text-xs text-text-muted">
                          {c.title}
                          {verified ? " · verified email" : ""}
                        </p>
                      </div>
                      <GhostButton
                        icon={Send}
                        onClick={() => router.push(outreachHref(c.id))}
                      >
                        Draft outreach
                      </GhostButton>
                    </div>
                  );
                })}
              </div>
            </section>
          ) : null}
        </article>
      ) : null}
    </AppShell>
  );
}
