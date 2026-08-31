"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
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
        const response = await apiFetch(`/api/v1/outreach/${params.id}`);
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setDetail((await response.json()) as OutreachDetail);
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
  }, [params.id, router]);

  return (
    <AppShell active="outreach" wide>
      <Link
        href="/outreach"
        className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to outreach
      </Link>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {loading ? (
        <ListSkeleton rows={4} />
      ) : detail ? (
        <div className="space-y-4">
          <header>
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
          </header>

          {detail.body ? (
            <Card>
              <CardTitle>Message</CardTitle>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                {detail.body}
              </p>
            </Card>
          ) : null}

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
