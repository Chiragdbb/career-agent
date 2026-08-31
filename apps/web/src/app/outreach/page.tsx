"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Outreach = {
  id: string;
  contact_id: string;
  status: string;
  subject: string | null;
};

export default function OutreachPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Outreach[]>([]);
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
        const response = await apiFetch("/api/v1/outreach");
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setRows((await response.json()) as Outreach[]);
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

  const columns = [
    { key: "to_contact", label: "To Contact" },
    { key: "drafted", label: "Drafted" },
    { key: "approved", label: "Approved" },
    { key: "sent", label: "Sent" },
  ];

  function columnForStatus(status: string) {
    const s = status.toLowerCase();
    if (s.includes("sent")) return "sent";
    if (s.includes("approved")) return "approved";
    if (s.includes("draft")) return "drafted";
    return "to_contact";
  }

  const grouped = columns.reduce(
    (acc, col) => {
      acc[col.key] = rows.filter((r) => columnForStatus(r.status) === col.key);
      return acc;
    },
    {} as Record<string, Outreach[]>,
  );

  return (
    <AppShell active="outreach" wide>
      <PageHeader
        title="Outreach"
        subtitle="Drafts and sent messages (approval required before send)."
      />
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      {loading ? (
        <CardGridSkeleton count={4} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No outreach yet"
          description="Draft messages to contacts will appear in this pipeline."
        />
      ) : (
        <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-4">
          {columns.map((col) => (
            <div
              key={col.key}
              className="flex min-w-[85vw] flex-1 snap-center flex-col gap-2 rounded-lg bg-muted p-3 sm:min-w-[200px]"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-muted-foreground">
                  {col.label}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {grouped[col.key]?.length ?? 0}
                </span>
              </div>
              {(grouped[col.key] ?? []).map((row) => (
                <Link
                  key={row.id}
                  href={`/outreach/${row.id}`}
                  className="rounded-md border border-border bg-card p-2.5 transition-shadow hover:shadow-sm"
                >
                  <p className="text-xs font-semibold text-foreground">
                    {row.subject || "Untitled outreach"}
                  </p>
                  <Badge variant="default" className="mt-2 text-[10px]">
                    {row.status}
                  </Badge>
                </Link>
              ))}
              {(grouped[col.key] ?? []).length === 0 ? (
                <p className="py-4 text-center text-[11px] text-muted-foreground">
                  Empty
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
