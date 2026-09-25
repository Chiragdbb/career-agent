"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Heart, Shield, Clock } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ActionCard } from "@/components/ui/ActionCard";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { Button, GhostButton, GoldButton } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { HeroBand } from "@/components/ui/HeroBand";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import {
  isDraftedOutreachStatus,
  outreachColumnForStatus,
} from "@/lib/outreach";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/cn";

type Outreach = {
  id: string;
  contact_id: string;
  status: string;
  subject: string | null;
  body?: string | null;
  reason?: string | null;
};

type FilterId = "all" | "draft" | "approved" | "sent";

export default function OutreachPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Outreach[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterId>("draft");

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

  const drafted = rows.filter((r) => isDraftedOutreachStatus(r.status));
  const sent = rows.filter((r) => outreachColumnForStatus(r.status) === "sent");
  const approved = rows.filter(
    (r) => outreachColumnForStatus(r.status) === "approved",
  );

  const filtered = useMemo(() => {
    if (filter === "draft") return drafted;
    if (filter === "approved") return approved;
    if (filter === "sent") return sent;
    return rows;
  }, [filter, drafted, approved, sent, rows]);

  const filters: { id: FilterId; label: string }[] = [
    { id: "all", label: `All mail (${rows.length})` },
    { id: "draft", label: `Draft (${drafted.length})` },
    { id: "approved", label: `Approved (${approved.length})` },
    { id: "sent", label: `Sent (${sent.length})` },
  ];

  return (
    <AppShell active="outreach" wide>
      <HeroBand className="mb-8">
        <div className="grid gap-8 lg:grid-cols-12 lg:items-center">
          <div className="lg:col-span-7">
            <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              Outbound{" "}
              <span className="font-serif italic text-coral">Mail hub.</span>
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-text-muted sm:text-[15px]">
              Drafts, approved notes, and sent mail for your applications. Nothing
              leaves without your seal.
            </p>
            <div className="mt-5 flex flex-wrap gap-4 text-sm font-semibold text-ink">
              <span className="inline-flex items-center gap-1.5">
                <Heart className="h-4 w-4 text-coral" /> {sent.length} sent
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Shield className="h-4 w-4 text-teal" /> Approval required
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-lavender-deep" />{" "}
                {drafted.length} drafts
              </span>
            </div>
          </div>
          <ActionCard className="lg:col-span-5 !bg-lavender/50">
            <p className="text-sm font-semibold text-lavender-deep">
              Package-linked outbound
            </p>
            <p className="mt-2 text-sm text-text-muted">
              Open a draft to jump back to Approvals when it belongs to a package.
              Send stays a separate step after approve.
            </p>
          </ActionCard>
        </div>
      </HeroBand>

      <div className="mb-6 flex gap-2 overflow-x-auto pb-1">
        {filters.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={cn(
              "shrink-0 rounded-full px-3.5 py-2 text-[13px] font-semibold transition-colors",
              filter === f.id
                ? "bg-white text-ink shadow-soft ring-1 ring-coral/30"
                : "text-text-muted hover:bg-white/70",
            )}
          >
            {filter === f.id && f.id === "draft" ? (
              <span className="mr-1.5 inline-block size-1.5 rounded-full bg-coral" />
            ) : null}
            {f.label}
          </button>
        ))}
      </div>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {actionError ? (
        <ErrorBanner
          message={actionError}
          onRetry={() => setActionError(null)}
          retryLabel="Dismiss"
        />
      ) : null}

      {loading ? (
        <CardGridSkeleton count={4} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No outbound mail yet"
          description="Hook emails from application packages land here as drafts. Approve, then send."
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-8">
            {filtered.length === 0 ? (
              <p className="rounded-2xl border border-line bg-white p-6 text-sm text-text-muted shadow-soft">
                Nothing in this filter.
              </p>
            ) : (
              filtered.map((row) => (
                <ActionCard key={row.id}>
                  <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <Link
                        href={`/outreach/${row.id}`}
                        className="text-lg font-bold text-ink hover:text-coral"
                      >
                        {row.subject || "Untitled outreach"}
                      </Link>
                      <div className="mt-2">
                        <SoftBadge tone="peach">{row.status}</SoftBadge>
                      </div>
                    </div>
                    {isDraftedOutreachStatus(row.status) ? (
                      <Button
                        type="button"
                        variant="secondary"
                        size="icon"
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
                  {row.reason ? (
                    <div className="mb-3 rounded-2xl bg-paper px-3 py-2 text-sm text-text-muted">
                      {row.reason}
                    </div>
                  ) : null}
                  <div className="rounded-2xl border border-line bg-paper/50 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-text-faint">
                      Draft preview
                    </p>
                    <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-ink">
                      {row.body?.trim() ||
                        "Open to read the full draft before approving or sending."}
                    </p>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {isDraftedOutreachStatus(row.status) ? (
                      <GoldButton
                        disabled={approvingId === row.id}
                        onClick={() => void approveFromKanban(row.id)}
                      >
                        Approve draft
                      </GoldButton>
                    ) : null}
                    <GhostButton onClick={() => router.push(`/outreach/${row.id}`)}>
                      Personalize
                    </GhostButton>
                  </div>
                </ActionCard>
              ))
            )}
          </div>

          <aside className="space-y-4 lg:col-span-4">
            <ActionCard>
              <h3 className="text-sm font-bold text-ink">Recent warm dialogues</h3>
              <ul className="mt-3 space-y-3">
                {sent.slice(0, 4).map((row) => (
                  <li key={row.id}>
                    <Link
                      href={`/outreach/${row.id}`}
                      className="block rounded-xl bg-paper px-3 py-2 hover:bg-lavender/40"
                    >
                      <p className="text-sm font-semibold text-ink">
                        {row.subject || "Sent note"}
                      </p>
                      <p className="text-xs text-text-muted">{row.status}</p>
                    </Link>
                  </li>
                ))}
                {sent.length === 0 ? (
                  <p className="text-xs text-text-muted">
                    Sent conversations will appear here.
                  </p>
                ) : null}
              </ul>
            </ActionCard>
            <ActionCard>
              <h3 className="text-sm font-bold text-ink">Your voice guardrails</h3>
              <ul className="mt-3 space-y-2 text-sm text-text-muted">
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-teal" />
                  Peer-to-peer framing
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-teal" />
                  Cite shared work when known
                </li>
                <li className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-teal" />
                  Never invent experience
                </li>
              </ul>
            </ActionCard>
            <div className="grid grid-cols-2 gap-2">
              <GhostButton
                className="!h-auto !flex-col !gap-1 !rounded-2xl !py-4"
                onClick={() => router.push("/contacts")}
              >
                <span className="text-xs font-bold">Draft custom</span>
                <span className="text-[10px] text-text-faint">via contacts</span>
              </GhostButton>
              <GhostButton
                className="!h-auto !flex-col !gap-1 !rounded-2xl !py-4"
                onClick={() => router.push("/approvals")}
              >
                <span className="text-xs font-bold">Approvals</span>
                <span className="text-[10px] text-text-faint">seal queue</span>
              </GhostButton>
            </div>
          </aside>
        </div>
      )}
    </AppShell>
  );
}
