"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock, Heart, Mic } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ActionCard } from "@/components/ui/ActionCard";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { Button, GhostButton, GoldButton } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { HeroBand } from "@/components/ui/HeroBand";
import { cn } from "@/lib/cn";
import { apiFetch } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type Interview = {
  id: string;
  application_id: string;
  status: string;
  title: string | null;
  scheduled_at: string | null;
  round: number | null;
  format: string | null;
  interviewer: string | null;
};

type Offer = {
  id: string;
  application_id: string;
  status: string;
  compensation: string | null;
  equity: string | null;
  location: string | null;
  offer_deadline: string | null;
};

type Application = {
  id: string;
  job_title: string | null;
  company_name: string | null;
};

function relativeInterviewTime(scheduledAt: string | null): string {
  if (!scheduledAt) return "Unscheduled";
  const date = new Date(scheduledAt);
  const diff = date.getTime() - Date.now();
  const days = Math.round(diff / (1000 * 60 * 60 * 24));
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days > 0 && days < 7) return `In ${days} days`;
  if (days < 0) return `${Math.abs(days)} days ago`;
  return date.toLocaleDateString();
}

function isNextUpcoming(interview: Interview, sorted: Interview[]): boolean {
  const upcoming = sorted.filter(
    (i) => i.scheduled_at && new Date(i.scheduled_at).getTime() >= Date.now(),
  );
  return upcoming[0]?.id === interview.id;
}

export default function InterviewsPage() {
  const router = useRouter();
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [applicationId, setApplicationId] = useState("");
  const [title, setTitle] = useState("Phone screen");

  async function reload() {
    const [iRes, oRes, aRes] = await Promise.all([
      apiFetch("/api/v1/interviews"),
      apiFetch("/api/v1/offers"),
      apiFetch("/api/v1/applications"),
    ]);
    if (!iRes.ok || !oRes.ok) {
      throw new Error("Failed to load interviews/offers");
    }
    setInterviews((await iRes.json()) as Interview[]);
    setOffers((await oRes.json()) as Offer[]);
    if (aRes.ok) {
      const apps = (await aRes.json()) as Application[];
      setApplications(apps);
      if (!applicationId && apps[0]) setApplicationId(apps[0].id);
    }
  }

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
        await reload();
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  const sortedInterviews = [...interviews].sort((a, b) => {
    if (!a.scheduled_at && !b.scheduled_at) return 0;
    if (!a.scheduled_at) return 1;
    if (!b.scheduled_at) return -1;
    return new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime();
  });

  const nextInterview = sortedInterviews.find(
    (i) => i.scheduled_at && new Date(i.scheduled_at).getTime() >= Date.now(),
  );

  const appFor = (applicationIdValue: string) =>
    applications.find((a) => a.id === applicationIdValue);

  async function onCreateInterview(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const response = await apiFetch("/api/v1/interviews", {
        method: "POST",
        body: JSON.stringify({
          application_id: applicationId,
          title,
          round: 1,
          format: "video",
          status: "scheduled",
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message || `API ${response.status}`);
      }
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  const readiness = Math.min(
    99,
    Math.round(
      ((sortedInterviews.filter((i) => i.status).length + 1) /
        Math.max(sortedInterviews.length + 1, 1)) *
        88,
    ),
  );

  return (
    <AppShell active="interviews" wide>
      <HeroBand className="mb-8">
        <div className="grid gap-8 lg:grid-cols-12 lg:items-center">
          <div className="lg:col-span-7">
            <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              Walk in{" "}
              <span className="font-serif italic text-coral">calm.</span> Walk in
              prepared.
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-text-muted sm:text-[15px]">
              Keep dossiers, schedules, and talking points in one place. Prep
              modules are scaffolding — your notes stay grounded in what you
              actually know.
            </p>
          </div>
          <ActionCard className="lg:col-span-5">
            <SoftBadge tone="peach" className="mb-2">
              Anchor reminder
            </SoftBadge>
            <p className="text-sm leading-relaxed text-ink">
              You&apos;re evaluating their engineering craft just as much as
              they&apos;re assessing yours.
            </p>
          </ActionCard>
        </div>
      </HeroBand>

      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}

      <div className="mb-8 grid gap-6 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-8">
          {nextInterview ? (
            <ActionCard highlight>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <SoftBadge tone="lavender">
                  Next sync · Round {nextInterview.round ?? "—"}
                </SoftBadge>
                <SoftBadge tone="coral">
                  {relativeInterviewTime(nextInterview.scheduled_at)}
                </SoftBadge>
              </div>
              <h2 className="text-xl font-bold text-ink">
                {nextInterview.title || "Interview"}
              </h2>
              <p className="mt-1 text-sm text-text-muted">
                {appFor(nextInterview.application_id)?.company_name ||
                  "Application"}{" "}
                · {appFor(nextInterview.application_id)?.job_title || ""}
              </p>
              {nextInterview.interviewer ? (
                <p className="mt-3 text-sm text-ink">
                  Interviewer: {nextInterview.interviewer}
                </p>
              ) : null}
              <div className="mt-4 rounded-2xl bg-paper p-4">
                <p className="text-[10px] font-bold uppercase tracking-wider text-text-faint">
                  Talking points
                </p>
                <ul className="mt-2 space-y-1.5 text-sm text-text-muted">
                  <li>Lead with verified work from your resume — no invented metrics.</li>
                  <li>Ask about team craft, ownership, and how decisions are made.</li>
                  <li>Bring one thoughtful trade-off story you actually lived.</li>
                </ul>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <GoldButton
                  onClick={() =>
                    router.push(`/applications/${nextInterview.application_id}`)
                  }
                >
                  Open application dossier
                </GoldButton>
                <GhostButton disabled title="Mock rehearsal is UI scaffolding only">
                  <Mic className="mr-1 h-3.5 w-3.5" />
                  Rehearsal (soon)
                </GhostButton>
              </div>
            </ActionCard>
          ) : null}

          {sortedInterviews
            .filter((i) => i.id !== nextInterview?.id)
            .map((i) => {
              const next = isNextUpcoming(i, sortedInterviews);
              const app = appFor(i.application_id);
              return (
                <ActionCard key={i.id}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap gap-2">
                        {next ? <SoftBadge tone="coral">Next up</SoftBadge> : null}
                        <SoftBadge tone="lavender">{i.status}</SoftBadge>
                      </div>
                      <h3 className="mt-2 text-lg font-bold text-ink">
                        {i.title || "Interview"}
                      </h3>
                      <p className="text-sm text-text-muted">
                        {app?.company_name} · Round {i.round ?? "—"} ·{" "}
                        {relativeInterviewTime(i.scheduled_at)}
                      </p>
                    </div>
                    <Link
                      href={`/applications/${i.application_id}`}
                      className="text-xs font-semibold text-coral"
                    >
                      Open dossier →
                    </Link>
                  </div>
                </ActionCard>
              );
            })}

          {!sortedInterviews.length ? (
            <EmptyState
              icon={CalendarClock}
              title="No interviews scheduled"
              description="Add an interview below once you have a real round on the calendar."
            />
          ) : null}

          <ActionCard>
            <h3 className="mb-3 text-sm font-bold text-ink">Add interview</h3>
            <form
              onSubmit={(e) => void onCreateInterview(e)}
              className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end"
            >
              <label className="w-full text-sm sm:min-w-[12rem] sm:flex-1">
                <span className="text-text-muted">Application</span>
                <select
                  className="mt-1 block w-full rounded-full border border-input bg-white px-3 py-2 text-sm"
                  value={applicationId}
                  onChange={(e) => setApplicationId(e.target.value)}
                  required
                >
                  {applications.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.job_title || a.id}{" "}
                      {a.company_name ? `· ${a.company_name}` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="w-full text-sm sm:min-w-[10rem]">
                <span className="text-text-muted">Title</span>
                <input
                  className="mt-1 block w-full rounded-full border border-input bg-white px-3 py-2 text-sm"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              <Button
                type="submit"
                variant="secondary"
                disabled={!applicationId}
                className="w-full sm:w-auto"
              >
                Add interview
              </Button>
            </form>
          </ActionCard>
        </div>

        <aside className="space-y-4 lg:col-span-4">
          <ActionCard>
            <p className="text-xs font-semibold uppercase tracking-wide text-text-faint">
              Preparation vitality
            </p>
            <div className="mt-3 flex items-center gap-3">
              <div
                className={cn(
                  "flex size-16 items-center justify-center rounded-full border-4 border-lavender text-lg font-bold text-ink",
                )}
              >
                {readiness}
              </div>
              <div>
                <p className="font-semibold text-ink">{readiness}% ready</p>
                <p className="text-xs text-text-muted">
                  Based on scheduled rounds on file — not a fabricated score.
                </p>
              </div>
            </div>
          </ActionCard>
          <ActionCard>
            <h3 className="text-sm font-bold text-ink">Practice toolkit</h3>
            <ul className="mt-3 space-y-3 text-sm">
              <li className="rounded-xl bg-paper px-3 py-2">
                <p className="font-semibold text-ink">Mock simulator</p>
                <p className="text-xs text-text-faint">Coming soon — UI only</p>
              </li>
              <li className="rounded-xl bg-paper px-3 py-2">
                <p className="font-semibold text-ink">Compensation notes</p>
                <Link href="/preferences" className="text-xs font-semibold text-coral">
                  Review preferences →
                </Link>
              </li>
              <li className="rounded-xl bg-paper px-3 py-2">
                <p className="font-semibold text-ink">Questions to ask them</p>
                <p className="text-xs text-text-muted">
                  Prefer curiosity about craft over performance theater.
                </p>
              </li>
            </ul>
          </ActionCard>
          <ActionCard className="!bg-coral-bg/40">
            <div className="flex gap-2">
              <Heart className="mt-0.5 h-4 w-4 text-coral" />
              <p className="text-sm text-ink">
                Remember what you have already shipped under real constraints.
                Speak from evidence.
              </p>
            </div>
          </ActionCard>
          <ActionCard>
            <h3 className="text-sm font-bold text-ink">Offers</h3>
            <ul className="mt-3 space-y-2 text-sm text-text-muted">
              {offers.map((o) => (
                <li key={o.id}>
                  {o.status}
                  {o.compensation ? ` · ${o.compensation}` : ""}
                  {o.location ? ` · ${o.location}` : ""}
                </li>
              ))}
              {!offers.length ? <li>No offers yet</li> : null}
            </ul>
          </ActionCard>
        </aside>
      </div>
    </AppShell>
  );
}
