"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { MetricCard } from "@/components/ui/MetricCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { Sparkline } from "@/components/ui/Sparkline";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
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

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
        const response = await apiFetch("/api/v1/analytics/summary");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setData((await response.json()) as Analytics);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const primaryMetrics: (keyof Analytics)[] = [
    "applications_count",
    "interviews_count",
    "outreach_count",
    "offers_count",
  ];

  return (
    <AppShell active="analytics" wide>
      <PageHeader
        title="Analytics"
        subtitle="High-level counts across your career pipeline."
        actions={
          <span className="text-xs text-text-muted">All-time summary counts</span>
        }
      />

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <CardGridSkeleton count={4} />
      ) : data ? (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {primaryMetrics.map((key) => (
              <MetricCard
                key={key}
                label={metricLabels[key]}
                value={data[key]}
              />
            ))}
          </div>
          <Card className="p-5">
            <h2 className="mb-1 text-sm font-semibold text-ink">Applications sent</h2>
            <p className="mb-3 text-xs text-text-muted">
              Time-series chart requires backend support — showing current total.
            </p>
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
                color="#2E6B59"
              />
            </div>
          </Card>
          <Card>
            <h2 className="mb-4 text-sm font-semibold text-foreground">
              Pipeline breakdown
            </h2>
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {(Object.keys(data) as (keyof Analytics)[])
                .filter((k) => !primaryMetrics.includes(k))
                .map((key) => (
                  <div
                    key={key}
                    className="flex items-center justify-between border-b border-border py-2 text-sm"
                  >
                    <dt className="text-muted-foreground">{metricLabels[key]}</dt>
                    <dd className="font-semibold text-foreground">{data[key]}</dd>
                  </div>
                ))}
            </dl>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
