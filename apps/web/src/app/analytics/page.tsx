"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
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

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <AppNav active="analytics" />
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Analytics</h1>
        <p className="mt-2 text-sm text-zinc-600">
          High-level counts across your career pipeline.
        </p>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {data ? (
        <dl className="grid gap-3 sm:grid-cols-2">
          {Object.entries(data).map(([key, value]) => (
            <div key={key} className="rounded border border-zinc-200 p-4">
              <dt className="text-xs uppercase tracking-wide text-zinc-500">
                {key.replace(/_/g, " ")}
              </dt>
              <dd className="mt-2 text-2xl font-semibold text-zinc-900">
                {value}
              </dd>
            </div>
          ))}
        </dl>
      ) : !error ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : null}
    </main>
  );
}
