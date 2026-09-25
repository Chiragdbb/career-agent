"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Calendar,
  Mail,
  Timer,
  Zap,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ActivityBar } from "@/components/ActivityBar";
import { OnboardingChecklist, preferencesUnset } from "@/components/OnboardingChecklist";
import { ActionCard } from "@/components/ui/ActionCard";
import { GhostButton, GoldButton } from "@/components/ui/Button";
import { HeroBand } from "@/components/ui/HeroBand";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { MomentumOrb } from "@/components/ui/Illustrations";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { useProcessActivity } from "@/hooks/useProcessActivity";
import { formatWorkflowType } from "@/lib/workflows";
import { cn } from "@/lib/cn";

type Summary = {
  jobs_count: number;
  applications_count: number;
  open_human_tasks: number;
  unread_notifications: number;
  upcoming_interviews: number;
  pending_offers: number;
  open_follow_ups: number;
};

type ActionItem = {
  id: string;
  title: string;
  sub: string;
  href: string;
  cta: string;
  icon: React.ComponentType<{ className?: string }>;
};

function formatEyebrow() {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function relativeTime(date: Date): string {
  const diff = Date.now() - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  return date.toLocaleDateString();
}

function ScoreRing({ value }: { value: number }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;
  return (
    <div className="relative size-16 shrink-0">
      <svg className="size-full -rotate-90" viewBox="0 0 64 64" aria-hidden>
        <circle cx="32" cy="32" r={r} fill="none" stroke="#E2DFFF" strokeWidth="6" />
        <circle
          cx="32"
          cy="32"
          r={r}
          fill="none"
          stroke="#D63B20"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-ink">
        {value}%
      </span>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [userName, setUserName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [onboarding, setOnboarding] = useState({
    preferencesComplete: true,
    resumeComplete: true,
    jobsComplete: true,
  });
  const { activeRuns, events, refresh: refreshActivity } = useProcessActivity();

  const load = useCallback(async () => {
    const [sumRes, prefsRes, resumesRes, jobsRes] = await Promise.all([
      apiFetch("/api/v1/dashboard/summary"),
      apiFetch("/api/v1/preferences"),
      apiFetch("/api/v1/resumes"),
      apiFetch("/api/v1/jobs"),
    ]);
    if (!sumRes.ok) {
      const body = await sumRes.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${sumRes.status}`);
    }
    setSummary((await sumRes.json()) as Summary);
    if (prefsRes.ok) {
      const prefs = (await prefsRes.json()) as {
        settings: { target_roles?: string[]; locations?: string[] };
      };
      setOnboarding((prev) => ({
        ...prev,
        preferencesComplete: !preferencesUnset(prefs.settings),
      }));
    }
    if (resumesRes.ok) {
      const resumes = (await resumesRes.json()) as unknown[];
      setOnboarding((prev) => ({ ...prev, resumeComplete: resumes.length > 0 }));
    }
    if (jobsRes.ok) {
      const jobs = (await jobsRes.json()) as unknown[];
      setOnboarding((prev) => ({ ...prev, jobsComplete: jobs.length > 0 }));
    }
    void refreshActivity();
  }, [refreshActivity]);

  useEffect(() => {
    if (events.length === 0) return;
    void load();
  }, [events.length, load]);

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
        const name =
          (user.user_metadata?.full_name as string | undefined) ||
          user.email?.split("@")[0] ||
          "";
        if (!cancelled) setUserName(name);
        await load();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [router, load]);

  const actionItems = useMemo<ActionItem[]>(() => {
    if (!summary) return [];
    const items: ActionItem[] = [];
    if (summary.open_human_tasks > 0) {
      items.push({
        id: "human-tasks",
        title: `${summary.open_human_tasks} item${summary.open_human_tasks > 1 ? "s" : ""} need your seal`,
        sub: "Review drafts and paused workflows before anything leaves.",
        href: "/approvals",
        cta: "Open Approvals",
        icon: Zap,
      });
    }
    if (summary.open_follow_ups > 0) {
      items.push({
        id: "follow-ups",
        title: `${summary.open_follow_ups} follow-up${summary.open_follow_ups > 1 ? "s" : ""} ready`,
        sub: "Warm notes awaiting your read and approval.",
        href: "/outreach",
        cta: "Review notes",
        icon: Timer,
      });
    }
    if (summary.upcoming_interviews > 0) {
      items.push({
        id: "interviews",
        title: `${summary.upcoming_interviews} upcoming interview${summary.upcoming_interviews > 1 ? "s" : ""}`,
        sub: "Prep dossiers and talking points are waiting.",
        href: "/interviews",
        cta: "Open cockpit",
        icon: Calendar,
      });
    }
    if (summary.unread_notifications > 0) {
      items.push({
        id: "notifications",
        title: `${summary.unread_notifications} unread notification${summary.unread_notifications > 1 ? "s" : ""}`,
        sub: "Catch up without losing your place.",
        href: "/settings",
        cta: "View",
        icon: Mail,
      });
    }
    return items.slice(0, 4);
  }, [summary]);

  const feedItems = useMemo(() => {
    const rows: { id: string; time: Date; title: string }[] = [];
    for (const run of activeRuns) {
      rows.push({
        id: `run-${run.id}`,
        time: run.updated_at ? new Date(run.updated_at) : new Date(),
        title:
          (run.metadata?.status_message as string) ||
          `${formatWorkflowType(run.workflow_type)} — ${run.status}`,
      });
    }
    for (const event of events.slice(0, 8)) {
      rows.push({
        id: event.id,
        time: event.timestamp,
        title: event.message,
      });
    }
    return rows.sort((a, b) => b.time.getTime() - a.time.getTime()).slice(0, 6);
  }, [activeRuns, events]);

  const pace = useMemo(() => {
    if (!summary) return 0;
    const total =
      summary.jobs_count +
      summary.applications_count +
      summary.upcoming_interviews +
      1;
    const done = summary.applications_count + summary.upcoming_interviews;
    return Math.min(99, Math.round((done / total) * 100));
  }, [summary]);

  const firstName = userName.split(" ")[0] || userName;

  return (
    <AppShell active="dashboard" wide hideActivityBar>
      <div className="mb-4 flex justify-end">
        <ActivityBar inline className="mb-0" />
      </div>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      <HeroBand className="mb-8">
        <div className="grid gap-8 lg:grid-cols-12 lg:items-center">
          <div className="lg:col-span-7">
            <SoftBadge tone="white" className="mb-4 shadow-sm">
              <span className="size-2 rounded-full bg-coral" />
              {formatEyebrow()} · Intentional search
            </SoftBadge>
            <h1 className="text-3xl font-bold leading-[1.15] tracking-tight text-ink sm:text-4xl">
              {getGreeting()}
              {firstName ? `, ${firstName}` : ""}.
              <span className="mt-1 block text-coral">
                You&apos;ve got great momentum today.
              </span>
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-text-muted sm:text-[17px]">
              {summary
                ? `Your agent surfaced ${summary.jobs_count} roles and is holding ${summary.open_human_tasks + summary.open_follow_ups} items for your seal. Take a calm peek below whenever you are ready.`
                : "Whenever you’re ready, take a calm peek at what needs your touch."}
            </p>
            <div className="mt-6 flex max-w-xl items-center gap-4 rounded-[32px] bg-white/90 p-4 shadow-soft backdrop-blur">
              <ScoreRing value={pace} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-lg font-semibold text-ink">Target Pace</p>
                  <SoftBadge tone="lavender">Active search</SoftBadge>
                </div>
                <p className="mt-0.5 text-[13px] text-text-muted">
                  {summary
                    ? `${summary.applications_count} applications · ${summary.upcoming_interviews} interviews ahead`
                    : "Loading your trajectory…"}
                </p>
              </div>
              <Link
                href="/analytics"
                className="hidden shrink-0 text-xs font-semibold text-coral sm:inline-flex sm:items-center sm:gap-1"
              >
                View breakdown <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </div>
          <div className="relative flex min-h-[220px] items-center justify-center lg:col-span-5">
            <MomentumOrb className="absolute size-64 opacity-90 sm:size-72" />
            <div className="relative z-10 flex flex-col items-center gap-3">
              <SoftBadge tone="mint">Human approval required</SoftBadge>
              <SoftBadge tone="white">No auto-send</SoftBadge>
              <SoftBadge tone="lavender">
                {summary?.jobs_count ?? "—"} roles in view
              </SoftBadge>
            </div>
          </div>
        </div>
      </HeroBand>

      <OnboardingChecklist
        steps={[
          {
            id: "preferences",
            label: "Set your job preferences",
            href: "/preferences",
            complete: onboarding.preferencesComplete,
          },
          {
            id: "resume",
            label: "Upload your resume",
            href: "/documents?tab=resumes",
            complete: onboarding.resumeComplete,
          },
          {
            id: "discovery",
            label: "Run your first job discovery",
            href: "/jobs?discover=1",
            complete: onboarding.jobsComplete,
          },
          {
            id: "review",
            label: "Review matches and start a pipeline",
            href: "/jobs",
            complete: (summary?.applications_count ?? 0) > 0 || (summary?.jobs_count ?? 0) > 3,
          },
          {
            id: "approvals",
            label: "Approve application drafts",
            href: "/approvals",
            complete: (summary?.open_human_tasks ?? 0) === 0 && (summary?.applications_count ?? 0) > 0,
          },
        ]}
      />

      {!summary && !error ? <CardGridSkeleton count={2} className="mb-8" /> : null}

      <section className="mb-10">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold tracking-tight text-ink">
                Ready for Your Touch
              </h2>
              {actionItems.length > 0 ? (
                <SoftBadge tone="coral">{actionItems.length} items</SoftBadge>
              ) : null}
            </div>
            <p className="mt-1 text-sm text-text-muted">
              Your seal required before anything leaves your desk.
            </p>
          </div>
          <Link href="/approvals" className="text-sm font-semibold text-coral">
            Open Approvals →
          </Link>
        </div>

        {actionItems.length === 0 ? (
          <ActionCard>
            <p className="text-sm text-text-muted">
              You&apos;re all caught up. Run discovery or review your pipeline when
              you&apos;re ready.
            </p>
            <div className="mt-4">
              <GoldButton onClick={() => router.push("/jobs")}>
                Explore opportunities
              </GoldButton>
            </div>
          </ActionCard>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {actionItems.map((item) => {
              const Icon = item.icon;
              return (
                <ActionCard key={item.id}>
                  <div className="mb-4 flex items-start gap-3">
                    <div className="flex size-12 items-center justify-center rounded-2xl bg-coral-bg">
                      <Icon className="h-5 w-5 text-coral" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-ink">{item.title}</h3>
                      <p className="mt-1 text-sm text-text-muted">{item.sub}</p>
                    </div>
                  </div>
                  <div className="mt-auto flex flex-wrap gap-2 pt-4">
                    <Link href={item.href}>
                      <GoldButton>
                        {item.cta} <ArrowRight className="ml-1 h-3.5 w-3.5" />
                      </GoldButton>
                    </Link>
                    <GhostButton onClick={() => router.push(item.href)}>
                      Review
                    </GhostButton>
                  </div>
                </ActionCard>
              );
            })}
          </div>
        )}
      </section>

      <section className="mb-8">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-ink">
              Conversations &amp; Adventures
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              Your living story pipeline at a glance.
            </p>
          </div>
          <GhostButton onClick={() => router.push("/applications")}>
            View full pipeline
          </GhostButton>
        </div>

        {summary ? (
          <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                label: "Discovering",
                count: summary.jobs_count,
                hint: "roles under review",
                tone: "border-l-lavender-deep",
              },
              {
                label: "Ready for You",
                count: summary.open_human_tasks + summary.open_follow_ups,
                hint: "awaiting your seal",
                tone: "border-l-coral",
              },
              {
                label: "In Discussion",
                count: summary.applications_count,
                hint: "active applications",
                tone: "border-l-warning",
              },
              {
                label: "Offer Stage",
                count: summary.pending_offers,
                hint: "celebrations approaching",
                tone: "border-l-coral-deep",
              },
            ].map((stage) => (
              <div
                key={stage.label}
                className={cn(
                  "rounded-2xl border border-line border-l-4 bg-white p-4 shadow-soft",
                  stage.tone,
                )}
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
                  {stage.label}
                </p>
                <p className="mt-1 text-2xl font-bold text-ink">{stage.count}</p>
                <p className="text-xs text-text-muted">{stage.hint}</p>
              </div>
            ))}
          </div>
        ) : null}

        <div className="rounded-3xl border border-line bg-white p-5 shadow-soft">
          <h3 className="mb-3 text-sm font-semibold text-text-muted">Live activity</h3>
          {feedItems.length === 0 ? (
            <p className="text-sm text-text-muted">
              Workflow events from discovery and applications will appear here.
            </p>
          ) : (
            <ul className="space-y-3">
              {feedItems.map((item) => (
                <li key={item.id} className="flex gap-3 text-sm">
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-coral" />
                  <div>
                    <p className="text-ink">{item.title}</p>
                    <p className="text-xs text-text-faint">{relativeTime(item.time)}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </AppShell>
  );
}
