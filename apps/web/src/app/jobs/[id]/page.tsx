"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckCircle2,
  Loader2,
  MapPin,
  Send,
  Sparkles,
  Star,
  Target,
  XCircle,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { GoldButton, GhostButton, Button } from "@/components/ui/Button";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/cn";
import { createClient } from "@/lib/supabase/client";
import { useEventStream } from "@/lib/useEventStream";
import {
  cancelWorkflowRun,
  fetchWorkflowRun,
  isActiveWorkflow,
  WorkflowRun,
} from "@/lib/workflows";

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
    description: string | null;
    explanation: string | null;
    matched_skills: string[];
    possible_matches?: string[];
    missing_skills: string[];
    job_skills?: string[];
    company_domain?: string | null;
    source?: string | null;
    external_id?: string | null;
    employment_type?: string | null;
    remote_type?: string | null;
    seniority?: string | null;
    salary_min?: number | null;
    salary_max?: number | null;
    salary_currency?: string | null;
    requirements?: string[];
    posted_at?: string | null;
    last_scraped_at?: string | null;
    scraped_at?: string | null;
    job_status?: string | null;
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

type LogEntry = {
  id: string;
  time: Date;
  message: string;
  phase: "thinking" | "working" | "result" | "error";
  detail?: string | null;
};

function displayValue(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  return String(value);
}

function formatSalary(
  min: number | null | undefined,
  max: number | null | undefined,
  currency: string | null | undefined,
): string {
  if (min == null && max == null) return "—";
  const cur = currency || "";
  const fmt = (n: number) =>
    `${cur ? `${cur} ` : ""}${n.toLocaleString()}`;
  if (min != null && max != null) return `${fmt(min)} – ${fmt(max)}`;
  if (min != null) return `From ${fmt(min)}`;
  return `Up to ${fmt(max!)}`;
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function JobField({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] uppercase tracking-wide text-text-faint">{label}</dt>
      <dd className="mt-0.5 break-words text-[13px] text-ink">{value}</dd>
    </div>
  );
}

function RescrapeProgress({
  runId,
  onFinished,
}: {
  runId: string;
  onFinished: () => void;
}) {
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const seenRef = useRef(new Set<string>());
  const finishedRef = useRef(false);

  const appendLog = useCallback(
    (entry: Omit<LogEntry, "id" | "time"> & { id?: string }) => {
      const key = entry.id || `${entry.message}-${entry.phase}`;
      if (seenRef.current.has(key)) return;
      seenRef.current.add(key);
      setLog((prev) => [
        ...prev,
        {
          id: key,
          time: new Date(),
          message: entry.message,
          phase: entry.phase,
          detail: entry.detail,
        },
      ]);
    },
    [],
  );

  const refresh = useCallback(async () => {
    try {
      const runData = await fetchWorkflowRun(runId);
      setRun(runData);
      setError(null);
      if (runData.metadata?.status_message) {
        appendLog({
          id: `meta-${runData.metadata.current_step}-${runData.metadata.status_message}`,
          message: String(runData.metadata.status_message),
          phase: isActiveWorkflow(runData.status) ? "thinking" : "result",
        });
      }
      if (!isActiveWorkflow(runData.status) && !finishedRef.current) {
        finishedRef.current = true;
        onFinished();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load progress");
    }
  }, [runId, appendLog, onFinished]);

  useEventStream({
    onEvent: (event) => {
      if (event.type === "heartbeat") return;
      const payload = event.payload;
      if (payload?.workflow_run_id !== runId) return;

      if (event.type === "workflow_cancelled") {
        appendLog({
          id: `evt-cancelled-${runId}`,
          message: "Re-scrape cancelled",
          phase: "error",
        });
      }
      if (event.type === "workflow_progress" && payload.message) {
        const data = (payload.data as Record<string, unknown>) || {};
        const phase =
          (payload.phase as LogEntry["phase"]) ||
          (data.phase as LogEntry["phase"]) ||
          "thinking";
        const detailParts: string[] = [];
        if (data.url) detailParts.push(`url: ${String(data.url)}`);
        if (data.title) detailParts.push(`title: ${String(data.title)}`);
        if (data.chars != null) detailParts.push(`chars: ${String(data.chars)}`);
        if (data.error) detailParts.push(`error: ${String(data.error)}`);
        appendLog({
          id: `evt-${payload.step}-${payload.message}-${phase}`,
          message: String(payload.message),
          phase,
          detail: detailParts.length ? detailParts.join(" · ") : null,
        });
      }
      void refresh();
    },
  });

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!run || !isActiveWorkflow(run.status)) return;
    const timer = setInterval(() => void refresh(), 2000);
    return () => clearInterval(timer);
  }, [run, refresh]);

  const active = run ? isActiveWorkflow(run.status) : false;

  const handleCancel = useCallback(async () => {
    if (!active || cancelling) return;
    setCancelling(true);
    try {
      const updated = await cancelWorkflowRun(runId);
      setRun(updated);
      appendLog({
        id: `cancel-${runId}`,
        message: "Re-scrape cancelled",
        phase: "error",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel re-scrape");
    } finally {
      setCancelling(false);
    }
  }, [active, cancelling, runId, appendLog]);

  return (
    <div className="mb-4 rounded-xl border border-line-soft bg-paper-raised">
      <div className="flex items-center justify-between gap-2 border-b border-line-soft px-3.5 py-2.5">
        <p className="text-[12.5px] font-semibold text-ink">Re-scrape progress</p>
        {active ? (
          <Button
            type="button"
            variant="secondary"
            disabled={cancelling}
            className="px-2 py-1 text-[10px]"
            onClick={() => void handleCancel()}
          >
            {cancelling ? "Cancelling…" : "Cancel"}
          </Button>
        ) : null}
      </div>
      {error ? <p className="px-3.5 py-2 text-xs text-destructive">{error}</p> : null}
      <div className="max-h-48 overflow-y-auto px-3.5 py-2.5">
        {!run && !error ? (
          <div className="flex items-center gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
            <p className="text-xs text-text-muted">Starting re-scrape…</p>
          </div>
        ) : log.length === 0 ? (
          <p className="text-xs text-text-muted">Waiting for activity…</p>
        ) : (
          <ul className="space-y-2">
            {log.map((entry, index) => {
              const isLatest = index === log.length - 1 && active;
              return (
                <li key={entry.id} className="flex gap-2">
                  <div className="mt-0.5 shrink-0">
                    {entry.phase === "error" ? (
                      <XCircle className="h-3.5 w-3.5 text-destructive" />
                    ) : entry.phase === "result" ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-teal" />
                    ) : isLatest ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                    ) : (
                      <CheckCircle2 className="h-3.5 w-3.5 text-text-faint" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p
                      className={cn(
                        "text-xs leading-relaxed",
                        entry.phase === "error" ? "text-destructive" : "text-ink",
                        isLatest && entry.phase === "thinking" && "animate-pulse",
                      )}
                    >
                      {entry.message}
                    </p>
                    {entry.detail ? (
                      <p className="mt-0.5 break-all text-[10px] text-text-muted">
                        {entry.detail}
                      </p>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function JobDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const matchId = params.id;

  const [loading, setLoading] = useState(true);
  const [rescoring, setRescoring] = useState(false);
  const [rescrapeRunId, setRescrapeRunId] = useState<string | null>(null);
  const [rescrapeError, setRescrapeError] = useState<string | null>(null);
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

  async function onRescrape() {
    setRescrapeError(null);
    try {
      const response = await apiFetch(`/api/v1/jobs/${matchId}/rescrape`, {
        method: "POST",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const body = (await response.json()) as { workflow_run_id: string };
      setRescrapeRunId(body.workflow_run_id);
    } catch (err) {
      setRescrapeError(err instanceof Error ? err.message : "Re-scrape failed");
    }
  }

  async function onRescrapeFinished() {
    try {
      setWorkspace(await fetchWorkspace());
    } catch {
      /* keep existing workspace */
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
  const requirements = job?.requirements ?? [];
  const jobSkills = job?.job_skills ?? [];

  return (
    <AppShell active="jobs" wide>
      <Link
        href="/jobs"
        className="mb-3.5 inline-flex items-center gap-1.5 text-[12.5px] text-text-muted hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to jobs
      </Link>
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {rescrapeError ? (
        <ErrorBanner message={rescrapeError} onRetry={() => void onRescrape()} />
      ) : null}
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
                <span className="flex items-center gap-1.5 text-[13.5px] text-text-muted">
                  <Building2 className="h-3.5 w-3.5" /> {displayValue(job.company_name)}
                </span>
                <span className="flex items-center gap-1.5 text-[13.5px] text-text-muted">
                  <MapPin className="h-3.5 w-3.5" />
                  {[job.work_arrangement, job.location].filter(Boolean).join(" · ") || "—"}
                </span>
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
                onClick={() => void onRescrape()}
                className="hover:text-foreground"
              >
                Re-scrape listing
              </button>
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

          {rescrapeRunId ? (
            <RescrapeProgress
              runId={rescrapeRunId}
              onFinished={() => {
                void onRescrapeFinished();
              }}
            />
          ) : null}

          {job.explanation ? (
            <div className="mb-4 rounded-xl bg-teal-bg px-[18px] py-4">
              <div className="mb-1.5 flex items-center gap-1.5">
                <Target className="h-3.5 w-3.5 text-teal" />
                <span className="text-[12.5px] font-semibold text-teal">Why it matches</span>
              </div>
              <p className="whitespace-pre-line text-[13.5px] leading-relaxed text-[#254E42]">
                {job.explanation}
              </p>
            </div>
          ) : null}

          <section className="mb-5 rounded-xl border border-line-soft bg-paper-raised px-[18px] py-4">
            <h2 className="mb-3 font-serif text-[15.5px] font-semibold text-ink">
              Job details
            </h2>
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <JobField label="Title" value={displayValue(job.title)} />
              <JobField label="Company" value={displayValue(job.company_name)} />
              <JobField label="Company domain" value={displayValue(job.company_domain)} />
              <JobField label="Location" value={displayValue(job.location)} />
              <JobField label="Work arrangement" value={displayValue(job.work_arrangement)} />
              <JobField label="Remote type" value={displayValue(job.remote_type)} />
              <JobField label="Employment type" value={displayValue(job.employment_type)} />
              <JobField label="Seniority" value={displayValue(job.seniority)} />
              <JobField
                label="Salary"
                value={formatSalary(job.salary_min, job.salary_max, job.salary_currency)}
              />
              <JobField label="Currency" value={displayValue(job.salary_currency)} />
              <JobField label="Source" value={displayValue(job.source)} />
              <JobField label="External ID" value={displayValue(job.external_id)} />
              <JobField label="Listing status" value={displayValue(job.job_status)} />
              <JobField label="Match status" value={displayValue(job.status)} />
              <JobField label="Posted at" value={formatTimestamp(job.posted_at)} />
              <JobField label="Last scraped" value={formatTimestamp(job.last_scraped_at)} />
              <JobField label="Scraped at" value={formatTimestamp(job.scraped_at)} />
              <JobField label="URL" value={displayValue(job.url)} />
            </dl>
            <div className="mt-4">
              <p className="text-[11px] uppercase tracking-wide text-text-faint">Description</p>
              <p className="mt-1 whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink">
                {job.description?.trim() ? job.description : "—"}
              </p>
            </div>
            <div className="mt-4">
              <p className="text-[11px] uppercase tracking-wide text-text-faint">
                Requirements ({requirements.length})
              </p>
              {requirements.length ? (
                <ul className="mt-1 list-disc space-y-1 pl-5 text-[13px] text-ink">
                  {requirements.map((req) => (
                    <li key={req}>{req}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-[13px] text-text-muted">—</p>
              )}
            </div>
            <div className="mt-4">
              <p className="text-[11px] uppercase tracking-wide text-text-faint">
                Listed skills ({jobSkills.length})
              </p>
              <p className="mt-1 text-[13px] text-ink">
                {jobSkills.length ? jobSkills.join(", ") : "—"}
              </p>
            </div>
          </section>

          <div className="mb-5 flex flex-col gap-2.5">
            <CollapsibleSection
              title={`Matched skills (${job.matched_skills.length})`}
              tone="good"
              defaultOpen
              chips={job.matched_skills.length ? job.matched_skills : ["None listed"]}
            />
            {(job.possible_matches?.length ?? 0) > 0 ? (
              <CollapsibleSection
                title={`Possible matches (${job.possible_matches!.length})`}
                tone="neutral"
                defaultOpen={false}
                chips={job.possible_matches!}
              />
            ) : null}
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
