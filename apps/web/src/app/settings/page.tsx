"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Notification = {
  id: string;
  title: string | null;
  body: string | null;
  status: string;
  notification_type: string | null;
};

type Mailbox = {
  provider: string;
  status: string;
  email_address: string | null;
  has_encrypted_token: boolean;
  error: string | null;
};

export default function SettingsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [mailbox, setMailbox] = useState<Mailbox | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const [nRes, mRes] = await Promise.all([
      apiFetch("/api/v1/notifications?status=unread"),
      apiFetch("/api/v1/settings/mailbox"),
    ]);
    if (!nRes.ok) {
      const body = await nRes.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${nRes.status}`);
    }
    setNotifications((await nRes.json()) as Notification[]);
    if (mRes.ok) setMailbox((await mRes.json()) as Mailbox);
  }

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
  }, [router]);

  async function markAllRead() {
    setError(null);
    setMessage(null);
    try {
      const response = await apiFetch("/api/v1/notifications/read-all", {
        method: "POST",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setMessage("Marked all notifications read");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <AppNav active="settings" />
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Settings</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Notifications and mailbox connection status.
        </p>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {message ? <p className="text-sm text-emerald-700">{message}</p> : null}

      <section className="rounded border border-zinc-200 p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-medium text-zinc-900">Unread notifications</h2>
          <button
            type="button"
            onClick={() => void markAllRead()}
            className="rounded border border-zinc-300 px-3 py-1 text-sm"
          >
            Mark all read
          </button>
        </div>
        <ul className="mt-3 space-y-2 text-sm">
          {notifications.map((n) => (
            <li key={n.id}>
              <p className="font-medium text-zinc-800">{n.title}</p>
              <p className="text-zinc-600">{n.body}</p>
            </li>
          ))}
          {!notifications.length ? (
            <li className="text-zinc-500">No unread notifications</li>
          ) : null}
        </ul>
      </section>

      <section className="rounded border border-zinc-200 p-4 text-sm">
        <h2 className="font-medium text-zinc-900">Mailbox</h2>
        {mailbox ? (
          <dl className="mt-2 space-y-1 text-zinc-700">
            <div>
              <dt className="inline text-zinc-500">Provider: </dt>
              <dd className="inline">{mailbox.provider}</dd>
            </div>
            <div>
              <dt className="inline text-zinc-500">Status: </dt>
              <dd className="inline">{mailbox.status}</dd>
            </div>
            <div>
              <dt className="inline text-zinc-500">Email: </dt>
              <dd className="inline">{mailbox.email_address || "—"}</dd>
            </div>
          </dl>
        ) : (
          <p className="mt-2 text-zinc-500">Loading…</p>
        )}
        <p className="mt-3 text-xs text-zinc-500">
          Gmail/Outlook OAuth is stubbed — connect in a later step.
        </p>
      </section>
    </main>
  );
}
