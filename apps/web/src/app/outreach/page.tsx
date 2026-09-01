"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { outreachColumnForStatus } from "@/lib/outreach";
import { createClient } from "@/lib/supabase/client";

type Outreach = {
  id: string;
  contact_id: string;
  status: string;
  subject: string | null;
};

const columns = [
  { key: "to_contact", label: "To Contact" },
  { key: "drafted", label: "Drafted" },
  { key: "approved", label: "Approved" },
  { key: "sent", label: "Sent" },
];

export default function OutreachPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Outreach[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const loadRows = useCallback(async () => {
    const response = await apiFetch("/api/v1/outreach");
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    return (await response.json()) as Outreach[];
  }, []);

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
        const data = await loadRows();
        if (!cancelled) setRows(data);
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
  }, [router, loadRows]);

  async function approveFromKanban(id: string) {
    setActionError(null);
    setApprovingId(id);
    try {
      const response = await apiFetch(`/api/v1/outreach/${id}/approve`, {
        method: "POST",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      setRows(await loadRows());
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setApprovingId(null);
    }
  }

  const grouped = columns.reduce(
    (acc, col) => {
      acc[col.key] = rows.filter((r) => outreachColumnForStatus(r.status) === col.key);
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
      {actionError ? (
        <ErrorBanner message={actionError} onRetry={() => setActionError(null)} retryLabel="Dismiss" />
      ) : null}

      {loading ? (
        <CardGridSkeleton count={4} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No outreach drafted yet"
          description="Outreach drafts are created automatically during application workflows and research. Approved messages appear here before send."
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
                <div
                  key={row.id}
                  className="rounded-md border border-border bg-card p-2.5 transition-shadow hover:shadow-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <Link href={`/outreach/${row.id}`} className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-foreground">
                        {row.subject || "Untitled outreach"}
                      </p>
                    </Link>
                    {col.key === "drafted" ? (
                      <Button
                        type="button"
                        variant="secondary"
                        size="icon"
                        className="h-7 w-7 shrink-0"
                        disabled={approvingId === row.id}
                        title="Approve"
                        aria-label="Approve outreach"
                        onClick={() => void approveFromKanban(row.id)}
                      >
                        {approvingId === row.id ? (
                          <span className="text-[10px]">…</span>
                        ) : (
                          <Check className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    ) : null}
                  </div>
                  <Link href={`/outreach/${row.id}`}>
                    <Badge variant="default" className="mt-2 text-[10px]">
                      {row.status}
                    </Badge>
                  </Link>
                </div>
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
