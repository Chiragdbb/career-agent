"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Briefcase,
  Calendar,
  ChevronRight,
  FileCheck,
  Loader2,
  Mail,
  Sparkles,
  Timer,
  Zap,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { OnboardingChecklist, preferencesUnset } from "@/components/OnboardingChecklist";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { MetricCard } from "@/components/ui/MetricCard";
import { PipelineStepper } from "@/components/ui/PipelineStepper";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { useProcessActivity } from "@/hooks/useProcessActivity";
import {
  formatWorkflowType,
} from "@/lib/workflows";

type Summary = {
  jobs_count: number;
  applications_count: number;
  open_human_tasks: number;
  unread_notifications: number;
  upcoming_interviews: number;
  pending_offers: number;
  open_follow_ups: number;
};

type Notification = {
  id: string;
  title: string | null;
  body: string | null;
  status: string;
};

type ActionItem = {
  id: string;
  label: string;
  detail?: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  priority: "high" | "medium" | "low";
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

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [pipelineCounts, setPipelineCounts] = useState<Record<string, number>>({});
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [userName, setUserName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [onboarding, setOnboarding] = useState({
    preferencesComplete: true,
    resumeComplete: true,
    jobsComplete: true,
  });
  const { activeRuns, events, refresh: refreshActivity } = useProcessActivity();

  const load = useCallback(async () => {
    const [sumRes, notifRes, appsRes, prefsRes, resumesRes, jobsRes] = await Promise.all([
      apiFetch("/api/v1/dashboard/summary"),
      apiFetch("/api/v1/notifications?status=unread"),
      apiFetch("/api/v1/applications"),
      apiFetch("/api/v1/preferences"),
      apiFetch("/api/v1/resumes"),
      apiFetch("/api/v1/jobs"),
    ]);
    if (!sumRes.ok) {
      const body = await sumRes.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${sumRes.status}`);
    }
    setSummary((await sumRes.json()) as Summary);
    if (notifRes.ok) {
      setNotifications((await notifRes.json()) as Notification[]);
    }
    if (appsRes.ok) {
      const apps = (await appsRes.json()) as { status: string }[];
      const counts = { Saved: 0, Applied: 0, Screening: 0, Interview: 0, Offer: 0 };
      for (const app of apps) {
        const s = app.status.toLowerCase();
        if (s.includes("offer")) counts.Offer++;
        else if (s.includes("interview")) counts.Interview++;
        else if (s.includes("screen")) counts.Screening++;
        else if (s.includes("applied") || s.includes("submit")) counts.Applied++;
        else counts.Saved++;
      }
      setPipelineCounts(counts);
    }
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
      setOnboarding((prev) => ({
        ...prev,
        resumeComplete: resumes.length > 0,
      }));
    }
    if (jobsRes.ok) {
      const jobs = (await jobsRes.json()) as unknown[];
      setOnboarding((prev) => ({
        ...prev,
        jobsComplete: jobs.length > 0,
      }));
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
          "there";
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
        label: `${summary.open_human_tasks} automation${summary.open_human_tasks > 1 ? "s" : ""} need your input`,
        detail: "Review paused workflows",
        href: "/tasks",
        icon: Zap,
        priority: "high",
      });
    }
    if (summary.open_follow_ups > 0) {
      items.push({
        id: "follow-ups",
        label: `${summary.open_follow_ups} follow-up${summary.open_follow_ups > 1 ? "s" : ""} due`,
        detail: "Send or schedule outreach",
        href: "/outreach",
        icon: Timer,
        priority: "high",
      });
    }
    if (summary.upcoming_interviews > 0) {
      items.push({
        id: "interviews",
        label: `${summary.upcoming_interviews} upcoming interview${summary.upcoming_interviews > 1 ? "s" : ""}`,
        href: "/interviews",
        icon: Calendar,
        priority: "medium",
      });
    }
    if (summary.unread_notifications > 0) {
      items.push({
        id: "notifications",
        label: `${summary.unread_notifications} unread notification${summary.unread_notifications > 1 ? "s" : ""}`,
        href: "/settings",
        icon: Mail,
        priority: "medium",
      });
    }
    if (summary.jobs_count > 0) {
      items.push({
        id: "jobs",
        label: `${summary.jobs_count} discovered job${summary.jobs_count > 1 ? "s" : ""} to review`,
        href: "/jobs",
        icon: Sparkles,
        priority: "low",
      });
    }
    if (summary.applications_count > 0) {
      items.push({
        id: "applications",
        label: `${summary.applications_count} application${summary.applications_count > 1 ? "s" : ""} in pipeline`,
        href: "/applications",
        icon: FileCheck,
        priority: "low",
      });
    }
    return items;
  }, [summary]);

  const feedItems = useMemo(() => {
    const rows: {
      id: string;
      time: Date;
      title: string;
      detail?: string;
      variant?: "default" | "active" | "error";
    }[] = [];

    for (const run of activeRuns) {
      rows.push({
        id: `run-${run.id}`,
        time: run.updated_at ? new Date(run.updated_at) : new Date(),
        title: formatWorkflowType(run.workflow_type),
        detail:
          (run.metadata?.status_message as string) ||
          (run.metadata?.current_step as string) ||
          run.status,
        variant: "active",
      });
    }
    for (const event of events.slice(0, 12)) {
      rows.push({
        id: event.id,
        time: event.timestamp,
        title: event.message,
        detail: event.detail,
        variant: event.type === "workflow_failed" ? "error" : "default",
      });
    }
    return rows.sort((a, b) => b.time.getTime() - a.time.getTime()).slice(0, 12);
  }, [activeRuns, events]);

  return (
    <AppShell active="dashboard" wide>
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium tracking-wide text-muted-foreground">
            {formatEyebrow()}
          </p>
          <h1 className="mt-1 font-serif text-3xl leading-tight text-foreground sm:text-4xl">
            {getGreeting()}
            {userName ? `, ${userName}` : ""}
          </h1>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Your hiring command center — track pipeline, automations, and live
            workflow activity in one place.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link href="/applications">
            <Button variant="secondary">View pipeline</Button>
          </Link>
          <Link href="/jobs">
            <Button>
              <Briefcase className="mr-2 h-4 w-4" />
              Discover jobs
            </Button>
          </Link>
        </div>
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
        <section className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <MetricCard label="Applications" value={summary.applications_count} />
          <MetricCard label="Interviews" value={summary.upcoming_interviews} />
          <MetricCard
            label="Follow-ups"
            value={summary.open_follow_ups}
            changeVariant={summary.open_follow_ups > 0 ? "warning" : "muted"}
            change={summary.open_follow_ups > 0 ? "Needs action" : undefined}
          />
          <MetricCard label="Offers" value={summary.pending_offers} />
        </section>
      ) : !error ? (
        <CardGridSkeleton count={4} className="mb-6" />
      ) : null}

      {summary ? (
        <section className="mb-6">
          <Card>
            <CardHeader className="mb-1">
              <CardTitle>Application pipeline</CardTitle>
              <Link
                href="/applications"
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                View all
              </Link>
            </CardHeader>
            <PipelineStepper
              className="mt-2"
              steps={[
                { label: "Saved", count: pipelineCounts.Saved ?? 0 },
                { label: "Applied", count: pipelineCounts.Applied ?? 0 },
                { label: "Screening", count: pipelineCounts.Screening ?? 0 },
                { label: "Interview", count: pipelineCounts.Interview ?? 0 },
                { label: "Offer", count: pipelineCounts.Offer ?? 0 },
              ]}
            />
          </Card>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-5">
        <Card padding={false} className="overflow-hidden lg:col-span-2">
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle>Action required</CardTitle>
            <Badge variant={actionItems.length > 0 ? "warning" : "success"}>
              {actionItems.length}
            </Badge>
          </CardHeader>
          {actionItems.length === 0 ? (
            <p className="px-5 py-8 text-sm text-muted-foreground">
              You&apos;re all caught up. Run discovery or review your pipeline
              when you&apos;re ready.
            </p>
          ) : (
            <ul>
              {actionItems.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.id} className="border-b border-border last:border-0">
                    <Link
                      href={item.href}
                      className="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-muted/40"
                    >
                      <div
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${
                          item.priority === "high"
                            ? "bg-destructive/10 text-destructive"
                            : item.priority === "medium"
                              ? "bg-warning/10 text-warning"
                              : "bg-muted text-muted-foreground"
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-foreground">
                          {item.label}
                        </p>
                        {item.detail ? (
                          <p className="text-xs text-muted-foreground">{item.detail}</p>
                        ) : null}
                      </div>
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}

          {notifications.length > 0 ? (
            <div className="border-t border-border bg-muted/20 px-5 py-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Latest notifications
              </p>
              <ul className="space-y-2">
                {notifications.slice(0, 3).map((n) => (
                  <li key={n.id}>
                    <p className="text-sm font-medium text-foreground">{n.title}</p>
                    <p className="line-clamp-1 text-xs text-muted-foreground">{n.body}</p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Card>

        <Card padding={false} className="overflow-hidden lg:col-span-3">
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle>Live activity</CardTitle>
            {activeRuns.length > 0 ? (
              <span className="flex items-center gap-1.5 text-xs text-primary">
                <Loader2 className="h-3 w-3 animate-spin" />
                {activeRuns.length} running
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">Up to date</span>
            )}
          </CardHeader>
          {feedItems.length === 0 ? (
            <p className="px-5 py-8 text-sm text-muted-foreground">
              Workflow events from discovery, applications, and outreach will
              stream here in real time.
            </p>
          ) : (
            <ul className="max-h-[420px] overflow-y-auto">
              {feedItems.map((item) => (
                <li
                  key={item.id}
                  className="flex gap-3 border-b border-border px-5 py-3.5 last:border-0"
                >
                  <span className="w-14 shrink-0 pt-0.5 text-[11px] tabular-nums text-muted-foreground">
                    {item.time.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm text-foreground">{item.title}</p>
                      {item.variant === "active" ? (
                        <Badge variant="primary" className="capitalize">
                          running
                        </Badge>
                      ) : null}
                      {item.variant === "error" ? (
                        <Badge variant="error">failed</Badge>
                      ) : null}
                    </div>
                    {item.detail ? (
                      <p className="mt-0.5 text-xs text-muted-foreground">{item.detail}</p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </AppShell>
  );
}
