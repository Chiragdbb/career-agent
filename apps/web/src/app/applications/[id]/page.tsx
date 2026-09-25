"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Check, Circle, Loader2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/cn";
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

const ENGINE_LABELS: Record<string, string> = {
  PREPARED: "Draft prepared",
  AWAITING_APPROVAL: "Waiting for your approval",
  IN_PROGRESS: "In progress",
  REQUIRES_HUMAN: "Needs your attention",
  SUBMITTED: "Submitted",
  FAILED: "Failed",
  BLOCKED: "Blocked",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  in_progress: "In progress",
  submitted: "Submitted",
  interviewing: "Interviewing",
  offered: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

const PIPELINE_STEPS = [
  { key: "PREPARED", label: "Prepare draft" },
  { key: "AWAITING_APPROVAL", label: "Your approval" },
  { key: "IN_PROGRESS", label: "Working" },
  { key: "SUBMITTED", label: "Submitted" },
] as const;

function humanizeToken(value: string): string {
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatStatus(status: string): string {
  return STATUS_LABELS[status] || humanizeToken(status);
}

function formatEngineState(raw: unknown): string {
  const key = String(raw || "");
  return ENGINE_LABELS[key] || humanizeToken(key);
}

function formatWhen(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTimelineEvent(
  event: ApplicationDetail["events"][number],
): { title: string; detail?: string } {
  const type = event.event_type || "";
  const payload = event.payload || {};

  if (type.startsWith("engine_transition:")) {
    const transition = type.slice("engine_transition:".length);
    const [from, to] = transition.split("->");
    if (to && from) {
      return {
        title: formatEngineState(to),
        detail: from
          ? `Moved from ${formatEngineState(from).toLowerCase()}`
          : undefined,
      };
    }
    if (to || transition.startsWith("->")) {
      const target = to || transition.replace(/^->/, "");
      return { title: formatEngineState(target), detail: "Pipeline started" };
    }
  }

  if (type === "status_changed") {
    return {
      title: `Status updated to ${formatStatus(String(payload.to || payload.status || ""))}`,
    };
  }

  if (type === "document_attached") {
    return { title: "Document attached", detail: String(payload.filename || "") };
  }

  return {
    title: humanizeToken(type.replace(/:/g, " ")),
    detail:
      typeof payload.message === "string"
        ? payload.message
        : Object.keys(payload).length
          ? undefined
          : undefined,
  };
}

function engineStepIndex(engine: string): number {
  const idx = PIPELINE_STEPS.findIndex((s) => s.key === engine);
  if (idx >= 0) return idx;
  if (engine === "REQUIRES_HUMAN" || engine === "FAILED" || engine === "BLOCKED") {
    return 2;
  }
  return 0;
}

function badgeVariant(
  status: string,
): "default" | "success" | "warning" | "error" | "primary" {
  const s = status.toLowerCase();
  if (s === "submitted" || s === "offered") return "success";
  if (s === "in_progress" || s === "interviewing" || s === "draft") return "primary";
  if (s === "withdrawn" || s === "rejected" || s === "failed") return "error";
  return "default";
}

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

  const engineStatus = String(detail?.submission_evidence?.engine_status || "");
  const activeStep = engineStepIndex(engineStatus);
  const openTasks = useMemo(
    () => (detail?.human_tasks || []).filter((t) => t.status === "open"),
    [detail],
  );

  return (
    <AppShell active="applications" wide>
      <Link
        href="/applications"
        className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to applications
      </Link>
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {!detail && !error ? <ListSkeleton rows={4} /> : null}
      {detail ? (
        <article className="space-y-6">
          <header>
            <h1 className="font-serif text-2xl text-foreground">
              {detail.job_title || "Application"}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <p className="text-sm text-muted-foreground">{detail.company_name}</p>
              <Badge variant={badgeVariant(detail.status)}>
                {formatStatus(detail.status)}
              </Badge>
              {engineStatus ? (
                <span className="text-xs text-text-muted">
                  {formatEngineState(engineStatus)}
                </span>
              ) : null}
            </div>
          </header>

          <Section title="Progress">
            <ol className="space-y-3">
              {PIPELINE_STEPS.map((step, index) => {
                const done = index < activeStep || engineStatus === "SUBMITTED";
                const current =
                  index === activeStep && engineStatus !== "SUBMITTED";
                return (
                  <li key={step.key} className="flex items-start gap-3">
                    <span
                      className={cn(
                        "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
                        done
                          ? "border-coral bg-coral text-white"
                          : current
                            ? "border-coral text-coral"
                            : "border-line text-text-faint",
                      )}
                    >
                      {done ? (
                        <Check className="h-3.5 w-3.5" strokeWidth={3} />
                      ) : current ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Circle className="h-3 w-3" />
                      )}
                    </span>
                    <div>
                      <p
                        className={cn(
                          "text-sm font-medium",
                          done || current ? "text-ink" : "text-text-muted",
                        )}
                      >
                        {step.label}
                      </p>
                      {current ? (
                        <p className="text-xs text-text-muted">
                          {formatEngineState(engineStatus)}
                        </p>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ol>
            {openTasks.length > 0 ? (
              <div className="mt-4 rounded-2xl border border-coral/30 bg-coral-bg/40 px-4 py-3">
                <p className="text-sm font-semibold text-ink">Needs your seal</p>
                <ul className="mt-2 space-y-1">
                  {openTasks.map((t) => (
                    <li key={t.id}>
                      <Link
                        href="/approvals"
                        className="text-sm text-coral hover:underline"
                      >
                        {t.title || humanizeToken(t.task_type)} →
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </Section>

          <Section title="Status">
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-text-faint">Application</dt>
                <dd className="font-medium text-ink">{formatStatus(detail.status)}</dd>
              </div>
              <div>
                <dt className="text-text-faint">Pipeline</dt>
                <dd className="font-medium text-ink">
                  {engineStatus ? formatEngineState(engineStatus) : "Not started"}
                </dd>
              </div>
              {detail.submission_evidence?.reason ? (
                <div className="sm:col-span-2">
                  <dt className="text-text-faint">Note</dt>
                  <dd className="text-ink">{String(detail.submission_evidence.reason)}</dd>
                </div>
              ) : null}
            </dl>
            <p className="mt-3 text-xs text-text-muted">
              Submission is only marked complete when there is clear evidence it
              was sent — never from a stub alone.
            </p>
          </Section>

          <Section title="Timeline">
            {detail.events.length === 0 ? (
              <Empty>No activity recorded yet.</Empty>
            ) : (
              <ul className="space-y-3">
                {[...detail.events].reverse().map((event, idx) => {
                  const item = formatTimelineEvent(event);
                  return (
                    <li key={`${event.event_type}-${event.created_at}-${idx}`} className="flex gap-3">
                      <time className="w-24 shrink-0 text-[11px] tabular-nums text-text-faint">
                        {formatWhen(event.created_at)}
                      </time>
                      <div className="min-w-0">
                        <p className="text-sm text-ink">{item.title}</p>
                        {item.detail ? (
                          <p className="text-xs text-text-muted">{item.detail}</p>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>

          <Section title="Documents">
            {detail.documents.length === 0 ? (
              <Empty>No documents attached yet.</Empty>
            ) : (
              <ul className="space-y-2 text-sm">
                {detail.documents.map((d) => (
                  <li key={d.id} className="flex justify-between gap-3">
                    <span className="text-ink">{d.filename || "Untitled document"}</span>
                    <span className="text-text-muted">{formatStatus(d.status)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Outreach">
            {detail.outreach.length === 0 ? (
              <Empty>No outreach drafts yet.</Empty>
            ) : (
              <ul className="space-y-2 text-sm">
                {detail.outreach.map((o) => (
                  <li key={o.id} className="flex justify-between gap-3">
                    <span className="text-ink">{o.subject || "Untitled message"}</span>
                    <span className="text-text-muted">{formatStatus(o.status)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Follow-ups">
            {detail.follow_ups.length === 0 ? (
              <Empty>No follow-ups scheduled.</Empty>
            ) : (
              <ul className="space-y-2 text-sm">
                {detail.follow_ups.map((f) => (
                  <li key={f.id}>
                    <p className="text-ink">{f.subject || "Follow-up"}</p>
                    <p className="text-xs text-text-muted">
                      {formatStatus(f.status)}
                      {f.next_action_at ? ` · ${formatWhen(f.next_action_at)}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Interviews">
            {detail.interviews.length === 0 ? (
              <Empty>No interviews scheduled.</Empty>
            ) : (
              <ul className="space-y-2 text-sm">
                {detail.interviews.map((i) => (
                  <li key={i.id}>
                    <p className="text-ink">
                      {i.title || "Interview"}
                      {i.round != null ? ` · Round ${i.round}` : ""}
                    </p>
                    <p className="text-xs text-text-muted">
                      {formatStatus(i.status)}
                      {i.scheduled_at ? ` · ${formatWhen(i.scheduled_at)}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Offers">
            {detail.offers.length === 0 ? (
              <Empty>No offers yet.</Empty>
            ) : (
              <ul className="space-y-2 text-sm">
                {detail.offers.map((o) => (
                  <li key={o.id} className="text-ink">
                    {formatStatus(o.status)}
                  </li>
                ))}
              </ul>
            )}
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
      <div className="mt-3">{children}</div>
    </Card>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}
