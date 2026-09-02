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
import { GhostButton } from "@/components/ui/Button";
import { MetricCard } from "@/components/ui/MetricCard";
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

function ActionRequiredCard({
  title,
  sub,
  href,
  icon: Icon,
}: ActionItem) {
  return (
    <Link
      href={href}
      className="flex w-full items-center gap-3 rounded-r-[10px] border border-line border-l-[3px] border-l-brick bg-paper-raised px-4 py-3 text-left transition-colors hover:bg-paper"
    >
      <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-lg bg-brick-bg">
        <Icon className="h-[15px] w-[15px] text-brick" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[13.5px] font-medium text-ink">{title}</p>
        <p className="mt-px text-xs text-text-muted">{sub}</p>
      </div>
      <ArrowRight className="h-[15px] w-[15px] shrink-0 text-text-faint" />
    </Link>
  );
}

function LiveActivityRow({
  text,
  time,
  last,
}: {
  text: string;
  time: string;
  last?: boolean;
}) {
  return (
    <div className={cn("relative flex gap-2.5", !last && "pb-4")}>
      <div className="flex flex-col items-center">
        <span className="mt-1 h-[5px] w-[5px] shrink-0 rounded-full bg-text-faint" />
        {!last ? <span className="mt-1 w-px flex-1 bg-line-soft" /> : null}
      </div>
      <div className="pb-0.5">
        <p className="text-[12.5px] text-foreground">{text}</p>
        <p className="mt-px text-[11px] text-text-faint">{time}</p>
      </div>
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
        title: `${summary.open_human_tasks} automation${summary.open_human_tasks > 1 ? "s" : ""} need your input`,
        sub: "Review paused workflows",
        href: "/tasks",
        icon: Zap,
      });
    }
    if (summary.open_follow_ups > 0) {
      items.push({
        id: "follow-ups",
        title: `${summary.open_follow_ups} follow-up${summary.open_follow_ups > 1 ? "s" : ""} due`,
        sub: "Send or schedule outreach",
        href: "/outreach",
        icon: Timer,
      });
    }
    if (summary.upcoming_interviews > 0) {
      items.push({
        id: "interviews",
        title: `${summary.upcoming_interviews} upcoming interview${summary.upcoming_interviews > 1 ? "s" : ""}`,
        sub: "View schedule",
        href: "/interviews",
        icon: Calendar,
      });
    }
    if (summary.unread_notifications > 0) {
      items.push({
        id: "notifications",
        title: `${summary.unread_notifications} unread notification${summary.unread_notifications > 1 ? "s" : ""}`,
        sub: "Review in settings",
        href: "/settings",
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

  const overnightCount = actionItems.length + (feedItems.length > 0 ? 1 : 0);

  return (
    <AppShell active="dashboard" wide hideActivityBar>
      <header className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="font-serif text-[25px] font-semibold text-ink">
            {getGreeting()}
            {userName ? `, ${userName}` : ""}
          </h1>
          <p className="mt-1 text-[13.5px] text-text-muted">
            {formatEyebrow()}
            {overnightCount > 0
              ? ` — ${overnightCount} thing${overnightCount > 1 ? "s" : ""} moved forward overnight`
              : ""}
          </p>
        </div>
        <ActivityBar inline className="shrink-0" />
      </header>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

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
            href: "/jobs",
            complete: onboarding.jobsComplete,
          },
        ]}
      />

      {summary ? (
        <section className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard label="Jobs discovered" value={summary.jobs_count} />
          <MetricCard label="Applications active" value={summary.applications_count} />
          <MetricCard label="Interviews upcoming" value={summary.upcoming_interviews} />
          <MetricCard
            label="Follow-ups open"
            value={summary.open_follow_ups}
            change={summary.open_follow_ups > 0 ? "Needs action" : undefined}
            changeVariant={summary.open_follow_ups > 0 ? "warning" : "muted"}
          />
        </section>
      ) : !error ? (
        <CardGridSkeleton count={4} className="mb-5" />
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-2.5 flex items-center justify-between">
            <h2 className="font-serif text-[16.5px] font-semibold text-ink">
              Needs your attention
            </h2>
            {actionItems.length > 0 ? (
              <span className="rounded-full bg-brick-bg px-2 py-0.5 text-xs text-brick">
                {actionItems.length} open
              </span>
            ) : null}
          </div>
          {actionItems.length === 0 ? (
            <p className="rounded-xl border border-line bg-paper-raised px-4 py-8 text-sm text-text-muted">
              You&apos;re all caught up. Run discovery or review your pipeline when
              you&apos;re ready.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {actionItems.map((item) => (
                <ActionRequiredCard key={item.id} {...item} />
              ))}
            </div>
          )}
          <div className="mt-6 flex justify-end">
            <GhostButton icon={ArrowRight} onClick={() => router.push("/applications?view=board")}>
              View pipeline board
            </GhostButton>
          </div>
        </div>

        <div>
          <h2 className="mb-3 font-serif text-[14.5px] font-semibold text-text-muted">
            Live activity
          </h2>
          <div className="rounded-[10px] border border-line-soft bg-paper-raised px-4 py-3.5">
            {feedItems.length === 0 ? (
              <p className="text-[12.5px] text-text-muted">
                Workflow events from discovery and applications will appear here.
              </p>
            ) : (
              feedItems.map((item, i) => (
                <LiveActivityRow
                  key={item.id}
                  text={item.title}
                  time={relativeTime(item.time)}
                  last={i === feedItems.length - 1}
                />
              ))
            )}
          </div>
        </div>
      </section>
    </AppShell>
  );
}
