"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
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

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [sumRes, notifRes] = await Promise.all([
      apiFetch("/api/v1/dashboard/summary"),
      apiFetch("/api/v1/notifications?status=unread"),
    ]);
    if (!sumRes.ok) {
      const body = await sumRes.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${sumRes.status}`);
    }
    setSummary((await sumRes.json()) as Summary);
    if (notifRes.ok) {
      setNotifications((await notifRes.json()) as Notification[]);
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

  const cards = summary
    ? [
        { label: "Jobs", value: summary.jobs_count, href: "/jobs" },
        {
          label: "Applications",
          value: summary.applications_count,
          href: "/applications",
        },
        { label: "Open tasks", value: summary.open_human_tasks, href: "/tasks" },
        {
          label: "Unread",
          value: summary.unread_notifications,
          href: "/settings",
        },
        {
          label: "Interviews",
          value: summary.upcoming_interviews,
          href: "/interviews",
        },
        { label: "Offers", value: summary.pending_offers, href: "/interviews" },
        { label: "Contacts", value: summary.contacts_count, href: "/contacts" },
        { label: "Outreach", value: summary.outreach_count, href: "/outreach" },
      ]
    : [];

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 px-6 py-12">
      <AppNav active="dashboard" />
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Dashboard</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Pipeline overview with live updates when workflows change.
        </p>
        {live ? <p className="mt-1 text-xs text-emerald-700">{live}</p> : null}
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Link
            key={card.label}
            href={card.href}
            className="rounded border border-zinc-200 p-4 hover:border-zinc-400"
          >
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              {card.label}
            </p>
            <p className="mt-2 text-2xl font-semibold text-zinc-900">
              {card.value}
            </p>
          </Link>
        ))}
        {!summary && !error ? (
          <p className="text-sm text-zinc-500">Loading…</p>
        ) : null}
      </section>
      <section className="rounded border border-zinc-200 p-4">
        <div className="flex items-center justify-between">
          <h2 className="font-medium text-zinc-900">Unread notifications</h2>
          <Link href="/settings" className="text-sm text-zinc-600 hover:underline">
            Settings
          </Link>
        </div>
        {notifications.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">No unread notifications</p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {notifications.slice(0, 5).map((n) => (
              <li key={n.id} className="border-b border-zinc-100 pb-2">
                <p className="font-medium text-zinc-800">{n.title}</p>
                <p className="text-zinc-600">{n.body}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
