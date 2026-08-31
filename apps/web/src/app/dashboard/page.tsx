"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Calendar,
  ChevronRight,
  FileCheck,
  Sparkles,
  Timer,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { PipelineStepper } from "@/components/ui/PipelineStepper";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { useEventStream } from "@/lib/useEventStream";

type Summary = {
  jobs_count: number;
  applications_count: number;
  open_human_tasks: number;
  unread_notifications: number;
  upcoming_interviews: number;
  pending_offers: number;
  open_follow_ups: number;
  contacts_count: number;
  outreach_count: number;
  documents_count: number;
};

type Notification = {
  id: string;
  title: string | null;
  body: string | null;
  status: string;
  notification_type: string | null;
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

type AttentionItem = {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
  iconColor: string;
};

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [pipelineCounts, setPipelineCounts] = useState<Record<string, number>>({});
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [userName, setUserName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [sumRes, notifRes, appsRes] = await Promise.all([
      apiFetch("/api/v1/dashboard/summary"),
      apiFetch("/api/v1/notifications?status=unread"),
      apiFetch("/api/v1/applications"),
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
  }, []);

  useEventStream({
    onEvent: (event) => {
      if (event.type === "heartbeat") return;
      setLive(`Update: ${event.type}`);
      void load();
    },
  });

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

  const attentionItems: AttentionItem[] = summary
    ? [
        ...(summary.applications_count > 0
          ? [
              {
                label: `${summary.applications_count} applications in pipeline`,
                href: "/applications",
                icon: FileCheck,
                accent: "bg-primary",
                iconColor: "text-primary",
              },
            ]
          : []),
        ...(summary.open_follow_ups > 0
          ? [
              {
                label: `${summary.open_follow_ups} follow-ups due`,
                href: "/outreach",
                icon: Timer,
                accent: "bg-destructive",
                iconColor: "text-destructive",
              },
            ]
          : []),
        ...(summary.jobs_count > 0
          ? [
              {
                label: `${summary.jobs_count} discovered jobs`,
                href: "/jobs",
                icon: Sparkles,
                accent: "bg-chart-2",
                iconColor: "text-chart-2",
              },
            ]
          : []),
        ...(summary.upcoming_interviews > 0
          ? [
              {
                label: `${summary.upcoming_interviews} upcoming interview${summary.upcoming_interviews > 1 ? "s" : ""}`,
                href: "/interviews",
                icon: Calendar,
                accent: "bg-chart-4",
                iconColor: "text-chart-4",
              },
            ]
          : []),
      ]
    : [];

  const stats = summary
    ? [
        { label: "Applications", value: summary.applications_count },
        { label: "Interviews", value: summary.upcoming_interviews },
        { label: "Follow-ups", value: summary.open_follow_ups },
        { label: "Offers", value: summary.pending_offers },
      ]
    : [];

  return (
    <AppShell active="dashboard" wide>
      <div className="flex flex-col gap-4 pb-5 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between md:pb-7">
        <div className="min-w-0 flex flex-col gap-2">
          <p className="text-xs font-medium tracking-wide text-muted-foreground">
            {formatEyebrow()}
          </p>
          <h1 className="font-serif text-3xl leading-tight text-foreground sm:text-4xl">
            {getGreeting()}
            {userName ? `, ${userName}` : ""}
          </h1>
          <p className="max-w-lg text-sm leading-relaxed text-muted-foreground">
            Pipeline overview with live updates when workflows change.
            {live ? (
              <span className="ml-2 text-primary">{live}</span>
            ) : null}
          </p>
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <Link href="/applications" className="flex-1 sm:flex-none">
            <Button variant="secondary" className="w-full sm:w-auto">
              View Pipeline
            </Button>
          </Link>
          <Link href="/jobs" className="flex-1 sm:flex-none">
            <Button className="w-full sm:w-auto">Discover Jobs</Button>
          </Link>
        </div>
      </div>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      {summary ? (
        <div className="mb-5 grid grid-cols-2 gap-3 rounded-lg border border-border bg-card p-4 sm:flex sm:items-center sm:justify-between sm:gap-0 sm:px-6 sm:py-5">
          {stats.map((stat, i) => (
            <div key={stat.label} className="flex items-center gap-4 sm:gap-6">
              <div className="flex flex-col gap-0.5">
                <span className="font-serif text-2xl text-foreground sm:text-[28px]">
                  {stat.value}
                </span>
                <span className="text-xs text-muted-foreground">{stat.label}</span>
              </div>
              {i < stats.length - 1 ? (
                <div className="hidden h-8 w-px bg-border sm:block" />
              ) : null}
            </div>
          ))}
        </div>
      ) : !error ? (
        <CardGridSkeleton count={4} className="mb-5" />
      ) : null}

      {summary ? (
        <Card className="mb-5">
          <CardTitle>Application pipeline</CardTitle>
          <PipelineStepper
            className="mt-4"
            steps={[
              { label: "Saved", count: pipelineCounts.Saved ?? 0 },
              { label: "Applied", count: pipelineCounts.Applied ?? 0 },
              { label: "Screening", count: pipelineCounts.Screening ?? 0 },
              { label: "Interview", count: pipelineCounts.Interview ?? 0 },
              { label: "Offer", count: pipelineCounts.Offer ?? 0 },
            ]}
          />
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card padding={false} className="overflow-hidden">
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle>Needs your attention</CardTitle>
            <span className="text-xs text-primary">
              {attentionItems.length} items
            </span>
          </CardHeader>
          {attentionItems.length === 0 ? (
            <p className="px-5 py-6 text-sm text-muted-foreground">
              All caught up — nothing needs your attention right now.
            </p>
          ) : (
            <ul>
              {attentionItems.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.label} className="border-b border-border last:border-0">
                    <Link
                      href={item.href}
                      className="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-muted/50"
                    >
                      <div className={`h-8 w-0.5 rounded-sm ${item.accent}`} />
                      <Icon className={`h-4 w-4 shrink-0 ${item.iconColor}`} />
                      <span className="flex-1 text-[13px] text-foreground">
                        {item.label}
                      </span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader className="mb-0">
            <CardTitle>Unread notifications</CardTitle>
            <Link href="/settings" className="text-xs text-muted-foreground hover:text-foreground">
              Settings
            </Link>
          </CardHeader>
          {notifications.length === 0 ? (
            <p className="text-sm text-muted-foreground">No unread notifications</p>
          ) : (
            <ul className="space-y-3">
              {notifications.slice(0, 5).map((n) => (
                <li key={n.id} className="border-b border-border pb-3 last:border-0">
                  <p className="text-sm font-medium text-foreground">{n.title}</p>
                  <p className="text-sm text-muted-foreground">{n.body}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
