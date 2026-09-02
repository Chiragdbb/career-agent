"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Check, CheckCircle2, Pencil, Send } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { GoldButton, GhostButton } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ListSkeleton } from "@/components/ui/Skeleton";
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
  const [message, setMessage] = useState("");
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
        if (!cancelled) {
          setDetail(data);
          setMessage(data.body || "");
        }
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
      setMessage(updated.body || message);
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

  return (
    <AppShell active="outreach" wide>
      <Link
        href="/outreach"
        className="mb-3.5 inline-flex items-center gap-1.5 text-[12.5px] text-text-muted hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to outreach
      </Link>

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
        <div className="max-w-[640px]">
          <header className="mb-1.5">
            <h1 className="font-serif text-[19px] font-semibold text-ink">
              {detail.subject || "Outreach message"}
            </h1>
            {detail.recipient_email ? (
              <p className="mt-0.5 text-[12.5px] text-text-muted">
                To {detail.recipient_email}
              </p>
            ) : null}
          </header>

          <div className="my-5 grid grid-cols-3 gap-2">
            {COLUMNS.map((col) => (
              <div
                key={col}
                className="relative min-h-[58px] rounded-[10px] border border-line-soft bg-paper-raised px-2.5 pb-6 pt-2.5"
              >
                <div className="mb-1.5 text-[11px] capitalize text-text-faint">{col}</div>
                {statusCol === col ? (
                  <div className="animate-riseIn rounded-[7px] border border-gold/30 bg-paper px-2 py-1.5 text-[11.5px] text-ink">
                    {detail.subject || "This message"}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-[12.5px] font-semibold text-text-muted">
              <Pencil className="h-3 w-3" /> Message
            </span>
            <span className="text-[11.5px] text-text-faint">{message.length} characters</span>
          </div>

          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={!isDrafted}
            rows={9}
            className={cn(
              "w-full resize-y rounded-[10px] border border-line px-3.5 py-3.5 text-[13.5px] leading-relaxed text-foreground",
              isDrafted ? "bg-paper-raised" : "bg-paper text-text-muted",
            )}
            aria-label="Message body"
          />

          <div className="mt-4 flex items-center gap-2.5">
            {isSent ? (
              <div className="flex animate-riseIn items-center gap-2 text-teal">
                <CheckCircle2 className="h-[17px] w-[17px]" />
                <span className="text-[13.5px] font-medium">Sent</span>
              </div>
            ) : (
              <>
                <GoldButton
                  icon={Check}
                  loading={approving && isDrafted}
                  disabled={!isDrafted || sending}
                  onClick={() => void runAction("approve")}
                >
                  {isApproved ? "Approved" : "Approve"}
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

          {detail.reason ? (
            <p className="mt-4 text-xs text-text-muted">{detail.reason}</p>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}
