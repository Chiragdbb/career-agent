"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Application = {
  id: string;
  job_id: string;
  status: string;
  job_title: string | null;
  company_name: string | null;
  applied_at: string | null;
};

export default function ApplicationsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Application[]>([]);
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
        const response = await apiFetch("/api/v1/applications");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setRows((await response.json()) as Application[]);
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
      <AppNav active="applications" />
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Applications</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Track submission state, evidence, and follow-ups.
        </p>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
        {rows.map((row) => (
          <li key={row.id}>
            <Link
              href={`/applications/${row.id}`}
              className="block px-4 py-3 hover:bg-zinc-50"
            >
              <p className="font-medium text-zinc-900">
                {row.job_title || "Untitled role"}
              </p>
              <p className="text-sm text-zinc-600">
                {[row.company_name, row.status].filter(Boolean).join(" · ")}
              </p>
            </Link>
          </li>
        ))}
        {!rows.length && !error ? (
          <li className="px-4 py-6 text-sm text-zinc-500">No applications yet</li>
        ) : null}
      </ul>
    </main>
  );
}
