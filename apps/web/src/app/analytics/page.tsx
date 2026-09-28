"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { BarChart3, Briefcase, Send } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { HeroBand } from "@/components/ui/HeroBand";
import { MetricCard } from "@/components/ui/MetricCard";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { Sparkline } from "@/components/ui/Sparkline";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { GhostButton } from "@/components/ui/Button";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Analytics = {
  jobs_count: number;
  applications_count: number;
  contacts_count: number;
  outreach_count: number;
  interviews_count: number;
  offers_count: number;
  open_human_tasks: number;
  unread_notifications: number;
};

const metricLabels: Record<keyof Analytics, string> = {
  jobs_count: "Jobs discovered",
  applications_count: "Applications sent",
  contacts_count: "Contacts",
  outreach_count: "Outreach messages",
  interviews_count: "Interviews",
  offers_count: "Offers",
  open_human_tasks: "Open tasks",
  unread_notifications: "Unread notifications",
};

function isPipelineEmpty(data: Analytics): boolean {
  return (
    data.jobs_count === 0 &&
    data.applications_count === 0 &&
    data.contacts_count === 0 &&
    data.outreach_count === 0 &&
    data.interviews_count === 0 &&
    data.offers_count === 0
  );
}

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) {
        router.replace("/login");
        return;
      }
      const response = await apiFetch("/api/v1/analytics/summary");
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setData((await response.json()) as Analytics);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  const primaryMetrics: (keyof Analytics)[] = useMemo(
    () => ["applications_count", "interviews_count", "outreach_count", "offers_count"],
    [],
  );

  const empty = data ? isPipelineEmpty(data) : false;

  return (
    <AppShell active="analytics" wide>
      <HeroBand className="mb-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <SoftBadge tone="lavender" className="mb-3">
              Pipeline intelligence
            </SoftBadge>
            <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              Analytics{" "}
              <span className="font-serif italic text-coral">at a glance.</span>
            </h1>
            <p className="mt-3 max-w-xl text-sm text-text-muted">
              High-level counts across discovery, applications, outreach, and offers —
              all derived from your live workspace data.
            </p>
          </div>
          {!loading && data && !empty ? (
            <div className="flex flex-wrap gap-2">
              <GhostButton type="button" onClick={() => router.push("/jobs")}>
                View jobs
              </GhostButton>
              <GhostButton type="button" onClick={() => router.push("/applications")}>
                Applications
              </GhostButton>
            </div>
          ) : null}
        </div>
      </HeroBand>

      {error ? (
        <ErrorBanner message={error} onRetry={() => void load()} />
      ) : null}

      {loading ? (
        <CardGridSkeleton count={4} />
      ) : data && empty ? (
        <EmptyState
          icon={BarChart3}
          title="No pipeline data yet"
          description="Run job discovery and start applications to populate analytics. Your metrics will appear here as activity grows."
          primaryActionLabel="Discover jobs"
          actionHref="/jobs?discover=1"
        />
      ) : data ? (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {primaryMetrics.map((key) => (
              <MetricCard key={key} label={metricLabels[key]} value={data[key]} />
            ))}
          </div>

          <Card className="border-line bg-white p-5 shadow-soft">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-ink">Applications sent</h2>
                <p className="mt-1 text-xs text-text-muted">
                  Current total — time-series charts ship when historical snapshots are
                  enabled on the backend.
                </p>
              </div>
              {data.applications_count === 0 ? (
                <Link
                  href="/jobs"
                  className="text-xs font-semibold text-coral hover:underline"
                >
                  Browse jobs →
                </Link>
              ) : (
                <Link
                  href="/applications"
                  className="text-xs font-semibold text-coral hover:underline"
                >
                  Open pipeline →
                </Link>
              )}
            </div>
            <div className="flex items-end gap-4">
              <span className="font-serif text-3xl font-semibold text-ink">
                {data.applications_count}
              </span>
              <Sparkline
                points={[
                  0,
                  data.applications_count,
                  Math.max(0, data.applications_count - 1),
                  data.applications_count,
                ]}
                color="#5B54FF"
              />
            </div>
          </Card>

          <Card className="border-line bg-white shadow-soft">
            <h2 className="mb-4 px-5 pt-5 text-sm font-semibold text-ink">
              Pipeline breakdown
            </h2>
            <dl className="grid gap-0 sm:grid-cols-2 lg:grid-cols-4">
              {(Object.keys(data) as (keyof Analytics)[])
                .filter((k) => !primaryMetrics.includes(k))
                .map((key) => (
                  <div
                    key={key}
                    className="flex items-center justify-between border-t border-line px-5 py-3 text-sm"
                  >
                    <dt className="text-text-muted">{metricLabels[key]}</dt>
                    <dd className="font-semibold tabular-nums text-ink">{data[key]}</dd>
                  </div>
                ))}
            </dl>
          </Card>

          {data.jobs_count > 0 && data.applications_count === 0 ? (
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-coral/25 bg-coral-bg/40 px-5 py-4">
              <Briefcase className="h-5 w-5 shrink-0 text-coral" />
              <p className="min-w-0 flex-1 text-sm text-text-muted">
                You have saved jobs but no applications yet — start one to move the needle.
              </p>
              <GhostButton
                type="button"
                icon={Send}
                onClick={() => router.push("/applications")}
              >
                View applications
              </GhostButton>
            </div>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}
