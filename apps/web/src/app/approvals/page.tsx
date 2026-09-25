"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, ChevronDown, Lock, Shield } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ActionCard } from "@/components/ui/ActionCard";
import { DiffPane } from "@/components/ui/DiffPane";
import { EmptyState } from "@/components/ui/EmptyState";
import { GhostButton, GoldButton } from "@/components/ui/Button";
import { HeroBand } from "@/components/ui/HeroBand";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import {
  DEFAULT_PREFERENCE_SETTINGS,
  type PreferenceSettings,
} from "@/lib/preferences";
import { isDraftedOutreachStatus } from "@/lib/outreach";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/cn";

type HumanTask = {
  id: string;
  task_type: string;
  title: string | null;
  status: string;
  details: Record<string, unknown>;
  application_id: string | null;
  outreach_id: string | null;
};

type Outreach = {
  id: string;
  contact_id: string;
  status: string;
  subject: string | null;
  body?: string | null;
  reason?: string | null;
};

type ApplicationDetail = {
  id: string;
  status: string;
  job_title: string | null;
  company_name: string | null;
  job_description?: string | null;
  job_url?: string | null;
  job_match_id?: string | null;
  submission_evidence?: Record<string, unknown> | null;
  contacts?: {
    id: string;
    name: string;
    title?: string | null;
    status?: string;
  }[];
};

function Toggle({
  checked,
  onChange,
  disabled,
  label,
  description,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label: string;
  description: string;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-start justify-between gap-4 rounded-2xl border border-line bg-white p-4 shadow-sm",
        disabled && "cursor-not-allowed opacity-70",
      )}
    >
      <div>
        <p className="text-sm font-semibold text-ink">{label}</p>
        <p className="mt-1 text-xs text-text-muted">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-7 w-12 shrink-0 rounded-full transition-colors",
          checked ? "bg-coral" : "bg-line",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 size-6 rounded-full bg-white shadow transition-transform",
            checked ? "left-5" : "left-0.5",
          )}
        />
      </button>
    </label>
  );
}

export default function ApprovalsPage() {
  return (
    <Suspense
      fallback={
        <AppShell active="approvals" wide>
          <ListSkeleton rows={3} />
        </AppShell>
      }
    >
      <ApprovalsPageInner />
    </Suspense>
  );
}

function ApprovalsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const focusAppId = searchParams.get("application");
  const [tasks, setTasks] = useState<HumanTask[]>([]);
  const [outreach, setOutreach] = useState<Outreach[]>([]);
  const [settings, setSettings] = useState<PreferenceSettings>(
    DEFAULT_PREFERENCE_SETTINGS,
  );
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(focusAppId);
  const [detailCache, setDetailCache] = useState<
    Record<string, ApplicationDetail>
  >({});

  const load = useCallback(async () => {
    const [tasksRes, outreachRes, prefsRes] = await Promise.all([
      apiFetch("/api/v1/human-tasks?status=open"),
      apiFetch("/api/v1/outreach"),
      apiFetch("/api/v1/preferences"),
    ]);
    if (tasksRes.ok) setTasks((await tasksRes.json()) as HumanTask[]);
    if (outreachRes.ok) setOutreach((await outreachRes.json()) as Outreach[]);
    if (prefsRes.ok) {
      const body = (await prefsRes.json()) as { settings?: PreferenceSettings };
      if (body.settings) {
        setSettings({ ...DEFAULT_PREFERENCE_SETTINGS, ...body.settings });
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user) {
          router.replace("/login");
          return;
        }
        await load();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [router, load]);

  useEffect(() => {
    if (focusAppId) setExpandedId(focusAppId);
  }, [focusAppId]);

  const draftOutreach = useMemo(
    () => outreach.filter((o) => isDraftedOutreachStatus(o.status)),
    [outreach],
  );

  const applicationTasks = useMemo(
    () =>
      tasks.filter(
        (t) =>
          t.task_type === "approval_required_application" && t.application_id,
      ),
    [tasks],
  );

  const otherTasks = useMemo(
    () =>
      tasks.filter(
        (t) =>
          !(
            t.task_type === "approval_required_application" && t.application_id
          ),
      ),
    [tasks],
  );

  const pendingCount =
    applicationTasks.length + draftOutreach.length + otherTasks.length;

  async function loadDetail(appId: string) {
    setDetailCache((prev) => {
      if (prev[appId]) return prev;
      return prev;
    });
    const res = await apiFetch(`/api/v1/applications/${appId}`);
    if (!res.ok) return;
    const detail = (await res.json()) as ApplicationDetail;
    setDetailCache((prev) => ({ ...prev, [appId]: detail }));
  }

  async function toggleExpand(appId: string) {
    const next = expandedId === appId ? null : appId;
    setExpandedId(next);
    if (next) void loadDetail(next);
  }

  useEffect(() => {
    if (expandedId) void loadDetail(expandedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expandedId]);

  async function softDiscard(
    appId: string,
    action: "return-to-pile" | "dismiss",
  ) {
    setBusyId(`${action === "dismiss" ? "dismiss" : "pile"}-${appId}`);
    setError(null);
    try {
      const response = await apiFetch(
        `/api/v1/applications/${appId}/${action}`,
        { method: "POST" },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setExpandedId(null);
      await load();
      setMessage(
        action === "dismiss"
          ? "Package dismissed."
          : "Returned to the job pile.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to discard package");
    } finally {
      setBusyId(null);
    }
  }

  async function rescrapeContacts(appId: string, matchId: string) {
    setBusyId(`rescrape-${appId}`);
    setError(null);
    try {
      const response = await apiFetch(`/api/v1/jobs/${matchId}/rescrape`, {
        method: "POST",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setMessage("Re-scrape queued — check Activity for progress.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to re-scrape");
    } finally {
      setBusyId(null);
    }
  }

  async function finalizeTask(taskId: string) {
    setBusyId(taskId);
    setError(null);
    try {
      const response = await apiFetch(`/api/v1/human-tasks/${taskId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resolution: { approved: true },
          resume_workflow: true,
          notes: "Finalized from Approvals",
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      await load();
      setMessage("Finalized — continuing prepare, submit, and outreach.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finalize");
    } finally {
      setBusyId(null);
    }
  }

  async function approveOutreach(id: string) {
    setBusyId(id);
    setError(null);
    try {
      const response = await apiFetch(`/api/v1/outreach/${id}/approve`, {
        method: "POST",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      await load();
      setMessage("Outreach approved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve");
    } finally {
      setBusyId(null);
    }
  }

  async function patchSettings(partial: Partial<PreferenceSettings>) {
    setSavingPrefs(true);
    setError(null);
    try {
      const next = { ...settings, ...partial };
      const response = await apiFetch("/api/v1/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: next }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setSettings(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences");
    } finally {
      setSavingPrefs(false);
    }
  }

  const scoutOn = settings.application_automation_mode !== "manual";
  const draftOn = settings.outreach_approval_mode !== "auto_when_rules";

  return (
    <AppShell active="approvals" wide>
      <HeroBand className="mb-8">
        <div className="grid gap-8 lg:grid-cols-12 lg:items-center">
          <div className="lg:col-span-7">
            <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              You hold the keys.{" "}
              <span className="text-coral">Always.</span>
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-text-muted sm:text-[15px]">
              Open a job below, check the draft, then Finalize. Want changes?
              Edit first.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <SoftBadge tone="lavender">
                <Shield className="h-3 w-3" /> Human approval required
              </SoftBadge>
              <SoftBadge tone="mint">No fabricated claims</SoftBadge>
            </div>
          </div>
          <div className="flex justify-center lg:col-span-5">
            <div className="flex size-48 flex-col items-center justify-center rounded-full bg-gradient-to-br from-coral-soft to-lavender shadow-card">
              <Lock className="mb-2 h-8 w-8 text-coral" />
              <p className="text-sm font-bold text-ink">Your stamp required</p>
              <p className="text-xs text-text-muted">Sovereign custody active</p>
            </div>
          </div>
        </div>
      </HeroBand>

      <div className="mb-8 grid gap-3 sm:grid-cols-3">
        <ActionCard>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
            Applications to seal
          </p>
          <p className="mt-1 text-3xl font-bold text-ink">
            {applicationTasks.length}
          </p>
          <p className="text-xs text-text-muted">Open a row → Finalize</p>
        </ActionCard>
        <ActionCard>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
            Notes to review
          </p>
          <p className="mt-1 text-3xl font-bold text-ink">{draftOutreach.length}</p>
          <p className="text-xs text-text-muted">Outreach awaiting approval</p>
        </ActionCard>
        <ActionCard>
          <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
            Other tasks
          </p>
          <p className="mt-1 text-3xl font-bold text-ink">{otherTasks.length}</p>
          <p className="text-xs text-text-muted">Captcha / misc</p>
        </ActionCard>
      </div>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {message ? <p className="mb-4 text-sm text-coral">{message}</p> : null}

      <section className="mb-10">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold tracking-tight text-ink">
            Applications ready for your seal
          </h2>
          <Link href="/jobs" className="text-sm font-semibold text-coral">
            Find more jobs →
          </Link>
        </div>

        {loading ? (
          <ListSkeleton rows={3} />
        ) : pendingCount === 0 ? (
          <EmptyState
            icon={CheckCircle2}
            title="Nothing needs your seal"
            description="Start applications from Jobs — they’ll show up here when ready."
            primaryActionLabel="Go to Jobs"
            actionHref="/jobs"
          />
        ) : (
          <div className="space-y-4">
            {applicationTasks.map((task) => {
              const appId = task.application_id!;
              const open = expandedId === appId;
              const detail = detailCache[appId];
              const materials =
                (detail?.submission_evidence?.draft_materials as
                  | Record<string, unknown>
                  | undefined) || {};
              const cover =
                (typeof materials.cover_letter === "string" &&
                  materials.cover_letter) ||
                (typeof materials.content === "string" && materials.content) ||
                null;
              const strategy =
                typeof materials.strategy_summary === "string"
                  ? materials.strategy_summary
                  : null;
              const contacts = detail?.contacts || [];

              return (
                <ActionCard key={task.id} highlight={open}>
                  <button
                    type="button"
                    className="flex w-full items-start justify-between gap-3 text-left"
                    onClick={() => void toggleExpand(appId)}
                  >
                    <div>
                      <h3 className="text-lg font-bold text-ink">
                        {task.title ||
                          detail?.job_title ||
                          "Application draft"}
                      </h3>
                      <p className="mt-1 text-sm text-text-muted">
                        {detail?.company_name
                          ? `${detail.company_name} · `
                          : ""}
                        Open to review, then Finalize
                      </p>
                    </div>
                    <ChevronDown
                      className={cn(
                        "mt-1 h-5 w-5 shrink-0 text-text-muted transition-transform",
                        open && "rotate-180",
                      )}
                    />
                  </button>

                  {open ? (
                    <div className="mt-4 space-y-4 border-t border-line pt-4">
                      {!detail ? (
                        <p className="text-sm text-text-muted">Loading draft…</p>
                      ) : (
                        <>
                          <div className="grid gap-4 lg:grid-cols-12">
                            <div className="lg:col-span-5">
                              <p className="text-xs font-semibold uppercase text-text-faint">
                                Job description
                              </p>
                              <div className="mt-1 max-h-56 overflow-y-auto whitespace-pre-wrap rounded-2xl border border-line bg-paper p-3 text-sm text-ink">
                                {detail.job_description ||
                                  "No job description captured yet."}
                              </div>
                              {detail.job_url ? (
                                <a
                                  href={detail.job_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="mt-2 inline-block text-xs font-semibold text-coral"
                                >
                                  Open original posting →
                                </a>
                              ) : null}
                            </div>
                            <div className="space-y-4 lg:col-span-7">
                              <div className="flex flex-wrap items-center gap-4">
                                {typeof materials.ats_score === "number" ? (
                                  <div className="flex items-center gap-3">
                                    <ScoreRing value={Number(materials.ats_score)} />
                                    <div>
                                      <p className="text-xs font-semibold uppercase text-text-faint">
                                        ATS score
                                      </p>
                                      <p className="text-sm text-text-muted">
                                        Keyword coverage vs this JD
                                      </p>
                                    </div>
                                  </div>
                                ) : null}
                              </div>
                              {typeof materials.hook_subject === "string" ||
                              typeof materials.hook_body === "string" ? (
                                <div>
                                  <p className="text-xs font-semibold uppercase text-text-faint">
                                    Hook email
                                  </p>
                                  {typeof materials.hook_subject === "string" ? (
                                    <p className="mt-1 text-sm font-semibold text-ink">
                                      {materials.hook_subject}
                                    </p>
                                  ) : null}
                                  <p className="mt-1 whitespace-pre-wrap text-sm text-ink">
                                    {(typeof materials.hook_body === "string" &&
                                      materials.hook_body) ||
                                      "—"}
                                  </p>
                                </div>
                              ) : null}
                              {strategy ? (
                                <div>
                                  <p className="text-xs font-semibold uppercase text-text-faint">
                                    Strategy
                                  </p>
                                  <p className="mt-1 text-sm text-ink">{strategy}</p>
                                </div>
                              ) : null}
                              <div>
                                <p className="text-xs font-semibold uppercase text-text-faint">
                                  Cover letter / note
                                </p>
                                <p className="mt-1 whitespace-pre-wrap text-sm text-ink">
                                  {cover ||
                                    "Draft text is still thin — Edit to restyle, or Finalize to continue."}
                                </p>
                              </div>
                              <div>
                                <p className="text-xs font-semibold uppercase text-text-faint">
                                  Contacts
                                </p>
                                {contacts.length === 0 ? (
                                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                                    <GhostButton
                                      className="justify-center"
                                      onClick={() => {
                                        if (detail.job_url) {
                                          window.open(detail.job_url, "_blank");
                                        }
                                      }}
                                      disabled={!detail.job_url}
                                    >
                                      Apply via job link
                                    </GhostButton>
                                    <GhostButton
                                      className="justify-center"
                                      disabled={
                                        !detail.job_match_id ||
                                        busyId === `rescrape-${appId}`
                                      }
                                      onClick={() =>
                                        void rescrapeContacts(
                                          appId,
                                          detail.job_match_id!,
                                        )
                                      }
                                    >
                                      {busyId === `rescrape-${appId}`
                                        ? "Re-scraping…"
                                        : "Scrape thoroughly again"}
                                    </GhostButton>
                                    <p className="sm:col-span-2 text-xs text-text-muted">
                                      No contacts yet — apply on the posting, or dig
                                      deeper for people. We never invent emails.
                                    </p>
                                  </div>
                                ) : (
                                  <ul className="mt-2 space-y-1 text-sm">
                                    {contacts.map((c) => (
                                      <li key={c.id || c.name} className="text-ink">
                                        {c.name}
                                        {c.title ? ` · ${c.title}` : ""}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            </div>
                          </div>
                        </>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <GoldButton
                          disabled={busyId === task.id}
                          onClick={() => void finalizeTask(task.id)}
                        >
                          {busyId === task.id
                            ? "Finalizing…"
                            : "Finalize this application"}
                        </GoldButton>
                        <GhostButton
                          onClick={() =>
                            router.push(`/applications/${appId}/edit`)
                          }
                        >
                          Edit
                        </GhostButton>
                        <GhostButton
                          disabled={busyId === `pile-${appId}`}
                          onClick={() => void softDiscard(appId, "return-to-pile")}
                        >
                          Back to pile
                        </GhostButton>
                        <GhostButton
                          disabled={busyId === `dismiss-${appId}`}
                          onClick={() => void softDiscard(appId, "dismiss")}
                        >
                          Dismiss
                        </GhostButton>
                      </div>
                    </div>
                  ) : null}
                </ActionCard>
              );
            })}

            {draftOutreach.map((row) => (
              <ActionCard key={row.id} highlight>
                <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h3 className="text-lg font-bold text-ink">
                      {row.subject || "Untitled outreach"}
                    </h3>
                    <SoftBadge tone="peach" className="mt-2">
                      {row.status}
                    </SoftBadge>
                  </div>
                </div>
                <DiffPane
                  leftLabel="Context / reason"
                  rightLabel="Draft ready for your seal"
                  left={
                    row.reason?.trim() ||
                    "No raw note captured — review the draft carefully."
                  }
                  right={
                    row.body?.trim() ||
                    "Open the conversation to read the full draft before approving."
                  }
                />
                <div className="mt-4 flex flex-wrap gap-2">
                  <GoldButton
                    disabled={busyId === row.id}
                    onClick={() => void approveOutreach(row.id)}
                  >
                    {busyId === row.id ? "Approving…" : "Approve draft"}
                  </GoldButton>
                  <GhostButton onClick={() => router.push(`/outreach/${row.id}`)}>
                    Personalize
                  </GhostButton>
                </div>
              </ActionCard>
            ))}

            {otherTasks.map((task) => (
              <ActionCard key={task.id}>
                <h3 className="text-lg font-bold text-ink">
                  {task.title || task.task_type}
                </h3>
                <p className="mt-1 text-sm text-text-muted">{task.task_type}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <GoldButton
                    disabled={busyId === task.id}
                    onClick={() => void finalizeTask(task.id)}
                  >
                    {busyId === task.id ? "Resolving…" : "Mark done & continue"}
                  </GoldButton>
                </div>
              </ActionCard>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-xl font-bold tracking-tight text-ink">
          Your Boundary Safeguards
        </h2>
        <p className="mb-4 text-sm text-text-muted">
          Auto-send stays off. Waypoint may draft; you decide what leaves.
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          <Toggle
            checked={scoutOn}
            disabled={savingPrefs}
            label="Scout roles in background"
            description="Allow assisted discovery beyond fully manual mode."
            onChange={(on) =>
              void patchSettings({
                application_automation_mode: on ? "assisted" : "manual",
              })
            }
          />
          <Toggle
            checked={draftOn}
            disabled={savingPrefs}
            label="Draft briefs & outreach notes"
            description="Keep per-item approval for outreach drafts."
            onChange={(on) =>
              void patchSettings({
                outreach_approval_mode: on ? "approve_each" : "always_approve",
              })
            }
          />
          <Toggle
            checked={false}
            disabled
            label="Automatically send applications"
            description="Disabled. Submissions require explicit evidence and your action."
            onChange={() => undefined}
          />
          <Toggle
            checked={false}
            disabled
            label="Automatically send outreach"
            description="Disabled. External messages always need your approval."
            onChange={() => undefined}
          />
        </div>
      </section>
    </AppShell>
  );
}
