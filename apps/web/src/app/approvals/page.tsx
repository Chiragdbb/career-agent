"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Lock, Shield } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ActionCard } from "@/components/ui/ActionCard";
import { DiffPane } from "@/components/ui/DiffPane";
import { EmptyState } from "@/components/ui/EmptyState";
import { GhostButton, GoldButton } from "@/components/ui/Button";
import { HeroBand } from "@/components/ui/HeroBand";
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

type Application = {
  id: string;
  status: string;
  job_title: string | null;
  company_name: string | null;
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
  const router = useRouter();
  const [tasks, setTasks] = useState<HumanTask[]>([]);
  const [outreach, setOutreach] = useState<Outreach[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [settings, setSettings] = useState<PreferenceSettings>(
    DEFAULT_PREFERENCE_SETTINGS,
  );
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [savingPrefs, setSavingPrefs] = useState(false);

  const load = useCallback(async () => {
    const [tasksRes, outreachRes, appsRes, prefsRes] = await Promise.all([
      apiFetch("/api/v1/human-tasks?status=open"),
      apiFetch("/api/v1/outreach"),
      apiFetch("/api/v1/applications"),
      apiFetch("/api/v1/preferences"),
    ]);
    if (tasksRes.ok) setTasks((await tasksRes.json()) as HumanTask[]);
    if (outreachRes.ok) setOutreach((await outreachRes.json()) as Outreach[]);
    if (appsRes.ok) setApplications((await appsRes.json()) as Application[]);
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

  const draftOutreach = useMemo(
    () => outreach.filter((o) => isDraftedOutreachStatus(o.status)),
    [outreach],
  );

  const signOffApps = useMemo(
    () =>
      applications.filter((a) => {
        const s = a.status.toLowerCase();
        return (
          s.includes("draft") ||
          s.includes("ready") ||
          s.includes("pending") ||
          s === "saved"
        );
      }),
    [applications],
  );

  const pendingCount = tasks.length + draftOutreach.length;

  async function resolveTask(taskId: string) {
    setBusyId(taskId);
    setError(null);
    try {
      const response = await apiFetch(`/api/v1/human-tasks/${taskId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resolution: { approved: true },
          resume_workflow: true,
          notes: "Resolved from Approvals",
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      await load();
      setMessage("Task resolved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed");
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
      setMessage("Outreach approved. Send still requires an explicit action.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusyId(null);
    }
  }

  async function patchSettings(patch: Partial<PreferenceSettings>) {
    const next = { ...settings, ...patch };
    setSettings(next);
    setSavingPrefs(true);
    setError(null);
    try {
      const response = await apiFetch("/api/v1/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: next }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setMessage("Boundary safeguards updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences");
      await load();
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
              Waypoint researches and drafts materials for you — but nothing is
              sent or submitted without your explicit approval.
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
            Pending seals
          </p>
          <p className="mt-1 text-3xl font-bold text-ink">{pendingCount}</p>
          <p className="text-xs text-text-muted">Drafts and paused workflows</p>
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
            Pipeline sign-off
          </p>
          <p className="mt-1 text-3xl font-bold text-ink">{signOffApps.length}</p>
          <p className="text-xs text-text-muted">Applications to inspect</p>
        </ActionCard>
      </div>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {message ? <p className="mb-4 text-sm text-coral">{message}</p> : null}

      <section className="mb-10">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold tracking-tight text-ink">
            Pending Your Express Seal
          </h2>
          <Link href="/activity" className="text-sm font-semibold text-coral">
            Activity log →
          </Link>
        </div>

        {loading ? (
          <ListSkeleton rows={3} />
        ) : pendingCount === 0 && signOffApps.length === 0 ? (
          <EmptyState
            icon={CheckCircle2}
            title="Nothing needs your seal"
            description="When drafts or paused workflows need you, they will appear here."
          />
        ) : (
          <div className="space-y-4">
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

            {tasks.map((task) => (
              <ActionCard key={task.id}>
                <h3 className="text-lg font-bold text-ink">
                  {task.title || task.task_type}
                </h3>
                <p className="mt-1 text-sm text-text-muted">{task.task_type}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <GoldButton
                    disabled={busyId === task.id}
                    onClick={() => void resolveTask(task.id)}
                  >
                    {busyId === task.id ? "Resolving…" : "Resolve & resume"}
                  </GoldButton>
                  {task.outreach_id ? (
                    <GhostButton
                      onClick={() =>
                        router.push(`/outreach/${task.outreach_id}`)
                      }
                    >
                      Open outreach
                    </GhostButton>
                  ) : null}
                  {task.application_id ? (
                    <GhostButton
                      onClick={() =>
                        router.push(`/applications/${task.application_id}`)
                      }
                    >
                      Open application
                    </GhostButton>
                  ) : null}
                </div>
              </ActionCard>
            ))}

            {signOffApps.slice(0, 4).map((app) => (
              <ActionCard key={app.id}>
                <SoftBadge tone="coral" className="mb-2">
                  Inspect before submit
                </SoftBadge>
                <h3 className="text-lg font-bold text-ink">
                  {app.job_title || "Untitled role"}
                </h3>
                <p className="text-sm text-text-muted">
                  {app.company_name} · {app.status}
                </p>
                <div className="mt-4">
                  <GoldButton
                    onClick={() => router.push(`/applications/${app.id}`)}
                  >
                    Inspect &amp; approve
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
