"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppNav } from "@/components/AppNav";
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
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-6 py-12">
      <AppNav active="applications" />
      <Link href="/applications" className="text-sm text-zinc-600 hover:text-zinc-900">
        ← Back to applications
      </Link>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {!detail && !error ? <p className="text-sm text-zinc-500">Loading…</p> : null}
      {detail ? (
        <article className="space-y-6">
          <header>
            <h1 className="text-2xl font-semibold text-zinc-900">
              {detail.job_title || "Application"}
            </h1>
            <p className="mt-1 text-sm text-zinc-600">
              {[detail.company_name, detail.status].filter(Boolean).join(" · ")}
            </p>
          </header>

          <Section title="Submission evidence">
            {detail.submission_evidence ? (
              <pre className="overflow-x-auto text-xs text-zinc-700">
                {JSON.stringify(detail.submission_evidence, null, 2)}
              </pre>
            ) : (
              <p className="text-sm text-zinc-500">No evidence recorded</p>
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
    </main>
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
    <section className="rounded border border-zinc-200 p-4">
      <h2 className="text-sm font-medium text-zinc-800">{title}</h2>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function EventList({ items }: { items: string[] }) {
  if (!items.length) {
    return <p className="text-sm text-zinc-500">None</p>;
  }
  return (
    <ul className="space-y-1 text-sm text-zinc-700">
      {items.map((item, idx) => (
        <li key={`${item}-${idx}`}>{item}</li>
      ))}
    </ul>
  );
}
