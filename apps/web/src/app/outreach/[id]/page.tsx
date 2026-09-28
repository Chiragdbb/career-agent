"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Send,
  Shield,
  UserRound,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ActionCard } from "@/components/ui/ActionCard";
import { GoldButton, GhostButton } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { apiFetch } from "@/lib/api";
import {
  isApprovedOutreachStatus,
  isDraftedOutreachStatus,
  outreachColumnForStatus,
} from "@/lib/outreach";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/cn";

type OutreachDetail = {
  id: string;
  contact_id: string;
  status: string;
  subject: string | null;
  body: string | null;
  recipient_email: string | null;
  reason: string | null;
  outreach_type: string | null;
};

const COLUMNS = ["drafted", "approved", "sent"] as const;

export default function OutreachDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [detail, setDetail] = useState<OutreachDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const [sending, setSending] = useState(false);
  const [lastAction, setLastAction] = useState<"approve" | "send" | null>(null);

  const loadDetail = useCallback(async () => {
    const response = await apiFetch(`/api/v1/outreach/${params.id}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message || `API ${response.status}`);
    }
    return (await response.json()) as OutreachDetail;
  }, [params.id]);

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
        const data = await loadDetail();
        if (!cancelled) setDetail(data);
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
  }, [params.id, router, loadDetail]);

  async function runAction(action: "approve" | "send") {
    setActionError(null);
    setLastAction(action);
    if (action === "approve") setApproving(true);
    else setSending(true);
    try {
      const response = await apiFetch(`/api/v1/outreach/${params.id}/${action}`, {
        method: "POST",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      const updated = (await response.json()) as OutreachDetail;
      setDetail(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : `${action} failed`);
    } finally {
      setApproving(false);
      setSending(false);
    }
  }

  const isDrafted = detail ? isDraftedOutreachStatus(detail.status) : false;
  const isApproved = detail ? isApprovedOutreachStatus(detail.status) : false;
  const isSent = detail ? outreachColumnForStatus(detail.status) === "sent" : false;
  const statusCol = detail ? outreachColumnForStatus(detail.status) : "drafted";
  const bodyText = detail?.body?.trim() || "";

  return (
    <AppShell active="outreach" wide>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/outreach"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to outreach
        </Link>
        {isDrafted ? (
          <Link
            href="/approvals"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-coral"
          >
            <Shield className="h-3.5 w-3.5" /> Approvals queue
          </Link>
        ) : null}
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {actionError ? (
        <ErrorBanner
          message={actionError}
          onRetry={() => lastAction && void runAction(lastAction)}
        />
      ) : null}

      {loading ? (
        <ListSkeleton rows={4} />
      ) : detail ? (
        <div className="grid gap-8 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-8">
            <header>
              <div className="flex flex-wrap items-center gap-2">
                {isDrafted ? (
                  <SoftBadge tone="ember">Awaiting your approval</SoftBadge>
                ) : null}
                <SoftBadge tone="lavender">{detail.status}</SoftBadge>
              </div>
              <h1 className="mt-3 text-2xl font-bold tracking-tight text-ink sm:text-3xl">
                {detail.subject || "Outreach message"}
              </h1>
              {detail.recipient_email ? (
                <p className="mt-2 text-sm text-text-muted">
                  To {detail.recipient_email}
                </p>
              ) : null}
            </header>

            <div className="grid grid-cols-3 gap-2">
              {COLUMNS.map((col) => (
                <div
                  key={col}
                  className={cn(
                    "relative min-h-[58px] rounded-2xl border px-3 pb-6 pt-2.5",
                    statusCol === col
                      ? "border-coral/40 bg-coral-bg/50"
                      : "border-line bg-paper",
                  )}
                >
                  <div className="mb-1.5 text-[11px] capitalize text-text-faint">
                    {col}
                  </div>
                  {statusCol === col ? (
                    <div className="rounded-xl border border-line bg-white px-2 py-1.5 text-[11.5px] text-ink">
                      Current stage
                    </div>
                  ) : null}
                </div>
              ))}
            </div>

            {detail.reason ? (
              <ActionCard className="!bg-paper">
                <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
                  Context
                </p>
                <p className="mt-2 text-sm leading-relaxed text-text-muted">
                  {detail.reason}
                </p>
              </ActionCard>
            ) : null}

            <ActionCard>
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-ink">Draft body</p>
                <span className="text-xs text-text-faint">
                  {bodyText.length} characters
                </span>
              </div>
              <div
                className="whitespace-pre-wrap rounded-2xl border border-line bg-paper px-4 py-3 text-sm leading-relaxed text-ink"
                aria-label="Message body"
              >
                {bodyText ||
                  "No body text yet — check Approvals or regenerate from the job package."}
              </div>
              <p className="mt-2 text-xs text-text-muted">
                Draft text comes from your workflow. Approve when it matches your voice;
                sending uses the stored draft on the server.
              </p>
            </ActionCard>

            <div className="flex flex-wrap items-center gap-2.5">
              {isSent ? (
                <div className="flex items-center gap-2 text-teal">
                  <CheckCircle2 className="h-[17px] w-[17px]" />
                  <span className="text-sm font-medium">Sent</span>
                </div>
              ) : (
                <>
                  <GoldButton
                    icon={Check}
                    loading={approving && isDrafted}
                    disabled={!isDrafted || sending}
                    onClick={() => void runAction("approve")}
                  >
                    {isApproved ? "Approved" : "Approve draft"}
                  </GoldButton>
                  <GhostButton
                    icon={Send}
                    disabled={!isApproved || approving || sending}
                    loading={sending && isApproved}
                    onClick={() => void runAction("send")}
                    className={isApproved ? "border-teal bg-teal-bg text-teal" : undefined}
                  >
                    Send
                  </GhostButton>
                </>
              )}
            </div>
          </div>

          <aside className="space-y-4 lg:col-span-4">
            <ActionCard>
              <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
                Recipient
              </p>
              <GhostButton
                className="mt-3 w-full justify-center"
                icon={UserRound}
                onClick={() => router.push(`/contacts/${detail.contact_id}`)}
              >
                Open contact profile
              </GhostButton>
            </ActionCard>
            {isDrafted ? (
              <ActionCard className="ring-1 ring-ember/20">
                <p className="text-sm font-semibold text-ink">Human approval</p>
                <p className="mt-2 text-sm text-text-muted">
                  This note stays internal until you approve. You can also seal it from
                  the Approvals hub alongside application packages.
                </p>
                <GoldButton
                  className="mt-4 w-full justify-center"
                  disabled={approving}
                  onClick={() => void runAction("approve")}
                >
                  {approving ? "Approving…" : "Approve from here"}
                </GoldButton>
              </ActionCard>
            ) : null}
          </aside>
        </div>
      ) : null}
    </AppShell>
  );
}
