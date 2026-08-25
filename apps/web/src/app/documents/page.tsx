"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Doc = {
  id: string;
  filename: string | null;
  status: string;
  mime_type: string | null;
};

export default function DocumentsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Doc[]>([]);
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
        const response = await apiFetch("/api/v1/documents");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setRows((await response.json()) as Doc[]);
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
      <AppNav active="documents" />
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Documents</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Resumes, cover letters, and application attachments.
        </p>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <ul className="divide-y divide-zinc-200 rounded border border-zinc-200">
        {rows.map((row) => (
          <li key={row.id} className="px-4 py-3 text-sm">
            <p className="font-medium text-zinc-900">
              {row.filename || row.id}
            </p>
            <p className="text-zinc-600">
              {[row.status, row.mime_type].filter(Boolean).join(" · ")}
            </p>
          </li>
        ))}
        {!rows.length && !error ? (
          <li className="px-4 py-6 text-sm text-zinc-500">No documents yet</li>
        ) : null}
      </ul>
    </main>
  );
}
