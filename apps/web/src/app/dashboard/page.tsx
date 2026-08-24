"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type MeResponse = {
  id: string;
  auth_subject: string;
  status: string;
};

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);

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
        if (!cancelled) setEmail(user.email ?? null);

        const response = await apiFetch("/api/v1/me");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        const payload = (await response.json()) as MeResponse;
        if (!cancelled) setMe(payload);
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

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-6 py-12">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-wide text-zinc-500">
            Career Agent
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-zinc-900">
            Dashboard
          </h1>
          <p className="mt-2 text-sm text-zinc-600">
            Auth placeholder — full product UI lands in a later step.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void signOut()}
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm"
        >
          Sign out
        </button>
      </div>

      <section className="rounded border border-zinc-200 p-4 text-sm">
        <h2 className="font-medium text-zinc-900">Session</h2>
        <p className="mt-2 text-zinc-600">Signed in as {email ?? "…"}</p>
      </section>

      <section className="rounded border border-zinc-200 p-4 text-sm">
        <h2 className="font-medium text-zinc-900">API /me (Bearer token)</h2>
        {error ? <p className="mt-2 text-red-600">{error}</p> : null}
        {me ? (
          <dl className="mt-2 space-y-1 text-zinc-700">
            <div>
              <dt className="inline text-zinc-500">Local user id: </dt>
              <dd className="inline font-mono text-xs">{me.id}</dd>
            </div>
            <div>
              <dt className="inline text-zinc-500">Auth subject: </dt>
              <dd className="inline font-mono text-xs">{me.auth_subject}</dd>
            </div>
            <div>
              <dt className="inline text-zinc-500">Status: </dt>
              <dd className="inline">{me.status}</dd>
            </div>
          </dl>
        ) : !error ? (
          <p className="mt-2 text-zinc-500">Loading…</p>
        ) : null}
      </section>
    </main>
  );
}
