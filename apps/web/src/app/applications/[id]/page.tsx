"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type ApplicationDetail = {
  id: string;
  status: string;
  job_title: string | null;
  company_name: string | null;
  submission_evidence: Record<string, unknown> | null;
  events: { event_type: string; created_at?: string; payload?: Record<string, unknown> }[];
  documents: { id: string; filename: string | null; status: string }[];
  outreach: { id: string; subject: string | null; status: string }[];
  follow_ups: { id: string; status: string; subject: string | null; next_action_at?: string }[];
  human_tasks: { id: string; title: string | null; status: string; task_type: string }[];
  interviews: {
    id: string;
    title: string | null;
    status: string;
    scheduled_at?: string | null;
    round?: number | null;
  }[];
  offers: { id: string; status: string; details: Record<string, unknown> }[];
};

export default function ApplicationDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
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
        const response = await apiFetch(`/api/v1/applications/${params.id}`);
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(body?.error?.message || `API ${response.status}`);
        }
        if (!cancelled) setDetail((await response.json()) as ApplicationDetail);
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
  }, [params.id, router]);

  return (
    <AppShell active="applications" wide>
      <Link href="/applications" className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground">
        ← Back to applications
      </Link>
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {!detail && !error ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {detail ? (
        <article className="space-y-6">
          <header>
            <h1 className="font-serif text-2xl text-foreground">
              {detail.job_title || "Application"}
            </h1>
            <div className="mt-2 flex items-center gap-2">
              <p className="text-sm text-muted-foreground">{detail.company_name}</p>
              <Badge variant="primary">{detail.status}</Badge>
            </div>
          </header>

          <Section title="Submission evidence">
            {detail.submission_evidence ? (
              <pre className="overflow-x-auto text-xs text-muted-foreground">
                {JSON.stringify(detail.submission_evidence, null, 2)}
              </pre>
            ) : (
              <p className="text-sm text-muted-foreground">No evidence recorded</p>
            )}
          </Section>

          <Section title="Timeline">
            <EventList
              items={detail.events.map((e) => `${e.event_type} · ${e.created_at || ""}`)}
            />
          </Section>

          <Section title="Documents">
            <EventList
              items={detail.documents.map(
                (d) => `${d.filename || d.id} (${d.status})`,
              )}
            />
          </Section>

          <Section title="Outreach">
            <EventList
              items={detail.outreach.map(
                (o) => `${o.subject || o.id} (${o.status})`,
              )}
            />
          </Section>

          <Section title="Follow-ups">
            <EventList
              items={detail.follow_ups.map(
                (f) => `${f.subject || f.id} · ${f.status} · ${f.next_action_at || ""}`,
              )}
            />
          </Section>

          <Section title="Human tasks">
            <EventList
              items={detail.human_tasks.map(
                (t) => `${t.title || t.task_type} (${t.status})`,
              )}
            />
          </Section>

          <Section title="Interviews">
            <EventList
              items={detail.interviews.map(
                (i) =>
                  `${i.title || "Interview"} · round ${i.round ?? "—"} · ${i.status}`,
              )}
            />
          </Section>

          <Section title="Offers">
            <EventList
              items={detail.offers.map(
                (o) => `${o.status} · ${JSON.stringify(o.details || {})}`,
              )}
            />
          </Section>
        </article>
      ) : null}
    </AppShell>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      <div className="mt-2">{children}</div>
    </Card>
  );
}

function EventList({ items }: { items: string[] }) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">None</p>;
  }
  return (
    <ul className="space-y-1 text-sm text-muted-foreground">
      {items.map((item, idx) => (
        <li key={`${item}-${idx}`}>{item}</li>
      ))}
    </ul>
  );
}
