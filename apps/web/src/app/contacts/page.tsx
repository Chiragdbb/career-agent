"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Contact = { id: string; name: string | null; status: string };

export default function ContactsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Contact[]>([]);
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
        const response = await apiFetch("/api/v1/contacts");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setRows((await response.json()) as Contact[]);
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
      <AppNav active="contacts" />
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Contacts</h1>
        <p className="mt-2 text-sm text-zinc-600">
          People linked to companies in your pipeline.
        </p>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
        {rows.map((row) => (
          <li key={row.id} className="px-4 py-3 text-sm">
            <p className="font-medium text-zinc-900">{row.name || "Unnamed"}</p>
            <p className="text-zinc-600">{row.status}</p>
          </li>
        ))}
        {!rows.length && !error ? (
          <li className="px-4 py-6 text-sm text-zinc-500">No contacts yet</li>
        ) : null}
      </ul>
    </main>
  );
}
