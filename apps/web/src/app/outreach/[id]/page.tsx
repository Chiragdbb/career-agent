"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import {
  isApprovedOutreachStatus,
  isDraftedOutreachStatus,
} from "@/lib/outreach";
import { createClient } from "@/lib/supabase/client";

type OutreachDetail = {
  id: string;
  contact_id: string;
  application_id: string | null;
  status: string;
  outreach_type: string | null;
  channel: string | null;
  subject: string | null;
  body: string | null;
  reason: string | null;
  recipient_email: string | null;
  delivery_state: string | null;
};

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
      setDetail((await response.json()) as OutreachDetail);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : `${action} failed`);
    } finally {
      setApproving(false);
      setSending(false);
    }
  }

  const isDrafted = detail ? isDraftedOutreachStatus(detail.status) : false;
  const isApproved = detail ? isApprovedOutreachStatus(detail.status) : false;

  return (
    <AppShell active="outreach" wide>
      <Link
        href="/outreach"
        className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to outreach
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
        <div className="space-y-4">
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="font-serif text-2xl text-foreground">
                {detail.subject || "Outreach"}
              </h1>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge variant="primary">{detail.status}</Badge>
                {detail.channel ? <Badge variant="default">{detail.channel}</Badge> : null}
                {detail.delivery_state ? (
                  <Badge variant="default">{detail.delivery_state}</Badge>
                ) : null}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                disabled={!isDrafted || approving || sending}
                onClick={() => void runAction("approve")}
              >
                {approving ? "Approving…" : "Approve"}
              </Button>
              <Button
                disabled={!isApproved || approving || sending}
                onClick={() => void runAction("send")}
              >
                {sending ? "Sending…" : "Send"}
              </Button>
            </div>
          </header>

          <Card>
            <CardTitle>Message</CardTitle>
            {detail.body ? (
              isDrafted ? (
                <textarea
                  readOnly
                  value={detail.body}
                  className="mt-3 w-full resize-y rounded-md border border-border bg-muted/30 px-3 py-2 text-sm leading-relaxed text-muted-foreground"
                  rows={8}
                  aria-label="Message body"
                />
              ) : (
                <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                  {detail.body}
                </p>
              )
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">No message body.</p>
            )}
          </Card>

          <Card>
            <CardTitle>Details</CardTitle>
            <dl className="mt-3 space-y-2 text-sm">
              {detail.recipient_email ? (
                <div className="flex flex-col gap-1 border-b border-border py-2 sm:flex-row sm:justify-between sm:gap-4">
                  <dt className="text-muted-foreground">Recipient</dt>
                  <dd className="break-all">{detail.recipient_email}</dd>
                </div>
              ) : null}
              {detail.reason ? (
                <div className="flex flex-col gap-1 border-b border-border py-2 sm:flex-row sm:justify-between sm:gap-4">
                  <dt className="text-muted-foreground">Reason</dt>
                  <dd className="sm:max-w-md sm:text-right">{detail.reason}</dd>
                </div>
              ) : null}
              {detail.outreach_type ? (
                <div className="flex flex-col gap-1 py-2 sm:flex-row sm:justify-between sm:gap-4">
                  <dt className="text-muted-foreground">Type</dt>
                  <dd className="capitalize">{detail.outreach_type}</dd>
                </div>
              ) : null}
            </dl>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
