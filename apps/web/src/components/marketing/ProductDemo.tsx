"use client";

import Link from "next/link";
import {
  Briefcase,
  CheckCircle2,
  FileText,
  Mail,
  Search,
  Shield,
} from "lucide-react";
import { useEffect, useState } from "react";

const steps = [
  {
    id: "discover",
    label: "Discover",
    icon: Search,
    title: "Pull roles that match your criteria",
    body: "Waypoint ingests listings from your sources, deduplicates them, and ranks fit against your profile — without inventing qualifications.",
  },
  {
    id: "tailor",
    label: "Tailor",
    icon: FileText,
    title: "Draft documents grounded in your history",
    body: "Resume and cover variants stay tied to verified experience. Every claim routes back to material you already uploaded.",
  },
  {
    id: "approve",
    label: "Approve",
    icon: Shield,
    title: "You seal every outbound action",
    body: "Applications and emails wait in an approval queue. Nothing submits or sends until you explicitly release it.",
  },
  {
    id: "track",
    label: "Track",
    icon: Briefcase,
    title: "Run the pipeline from one cockpit",
    body: "Interviews, tasks, outreach threads, and follow-ups stay connected to the job record — searchable and auditable.",
  },
] as const;

type StepId = (typeof steps)[number]["id"];

function DemoPanel({
  active,
  selectedJob,
  onSelectJob,
  released,
  onRelease,
}: {
  active: StepId;
  selectedJob: string;
  onSelectJob: (co: string) => void;
  released: boolean;
  onRelease: () => void;
}) {
  if (active === "discover") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {[
          { co: "Northwind Labs", role: "Staff Platform Engineer", score: 92 },
          { co: "Helio Systems", role: "Senior Backend Engineer", score: 88 },
          { co: "Arcadia Health", role: "Engineering Lead", score: 84 },
          { co: "Riverstone AI", role: "Applied ML Engineer", score: 79 },
        ].map((job) => {
          const selected = selectedJob === job.co;
          return (
            <button
              key={job.co}
              type="button"
              onClick={() => onSelectJob(job.co)}
              className={`rounded-xl border bg-white p-4 text-left transition ${
                selected
                  ? "border-mkt-indigo/40 shadow-[0_18px_40px_-24px_rgba(91,84,255,0.55)] ring-1 ring-mkt-indigo/20"
                  : "border-mkt-hairline hover:border-mkt-indigo/25 hover:bg-mkt-canvas-soft"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-mkt-ink">{job.co}</p>
                  <p className="mt-0.5 text-xs text-mkt-muted">{job.role}</p>
                </div>
                <span className="rounded-md bg-mkt-indigo/10 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-mkt-indigo">
                  {job.score}
                </span>
              </div>
              {selected ? (
                <p className="mt-3 text-[11px] font-medium text-mkt-indigo">
                  Selected · continue to Tailor
                </p>
              ) : null}
            </button>
          );
        })}
      </div>
    );
  }

  if (active === "tailor") {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-mkt-hairline bg-mkt-canvas-soft p-4">
          <p className="text-[11px] font-semibold text-mkt-muted">Source résumé</p>
          <ul className="mt-3 space-y-2 text-xs leading-relaxed text-mkt-ink">
            <li>• Led migration of billing service to event-driven architecture</li>
            <li>• Owned on-call rotation for payments API (99.95% uptime)</li>
            <li>• Mentored 4 engineers across two product squads</li>
          </ul>
        </div>
        <div className="rounded-xl border border-mkt-indigo/25 bg-white p-4">
          <p className="text-[11px] font-semibold text-mkt-indigo">
            Tailored for {selectedJob} — backend focus
          </p>
          <ul className="mt-3 space-y-2 text-xs leading-relaxed text-mkt-ink">
            <li>• Highlighted distributed systems work aligned to posting keywords</li>
            <li>• Reframed metrics already present in your master résumé</li>
            <li className="text-mkt-muted">No new employers, dates, or skills added</li>
          </ul>
          <button
            type="button"
            onClick={onRelease}
            className="mt-4 rounded-full bg-mkt-indigo px-4 py-2 text-xs font-semibold text-white hover:bg-mkt-indigo-deep"
          >
            Continue to Approve
          </button>
        </div>
      </div>
    );
  }

  if (active === "approve") {
    return (
      <div className="space-y-3">
        <div className="flex flex-col gap-3 rounded-xl border border-mkt-hairline bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-ember/10 text-ember">
              <Mail className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-mkt-ink">
                Outreach draft · {selectedJob}
              </p>
              <p className="text-xs text-mkt-muted">
                Warm intro referencing shared conference talk
              </p>
            </div>
          </div>
          {released ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Released in preview
            </span>
          ) : (
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={onRelease}
                className="rounded-full bg-mkt-indigo px-4 py-2 text-xs font-semibold text-white hover:bg-mkt-indigo-deep"
              >
                Review &amp; release
              </button>
              <Link
                href="/signup?from=demo-approve"
                className="rounded-full border border-mkt-hairline px-4 py-2 text-center text-xs font-semibold text-mkt-ink hover:bg-mkt-canvas-soft"
              >
                Sign up to send for real
              </Link>
            </div>
          )}
        </div>
        <div className="rounded-xl border border-dashed border-mkt-hairline bg-mkt-canvas-soft p-4 text-xs text-mkt-muted">
          Sample data only. Creating an account loads your own drafts into Approvals.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Applied", count: 6, href: "/signup?next=/applications" },
          { label: "Screen", count: 2, href: "/signup?next=/applications" },
          { label: "Interview", count: 1, href: "/signup?next=/interviews" },
          { label: "Offer", count: 0, href: "/signup?next=/applications" },
        ].map((col) => (
          <Link
            key={col.label}
            href={col.href}
            className="rounded-xl border border-mkt-hairline bg-mkt-canvas-soft p-3 transition hover:border-mkt-indigo/30 hover:bg-white"
          >
            <p className="text-[10px] font-semibold text-mkt-muted">{col.label}</p>
            <p className="mt-3 text-2xl font-semibold tabular-nums text-mkt-ink">
              {col.count}
            </p>
            <p className="mt-1 text-[11px] text-mkt-muted">Open in workspace →</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function ProductDemo() {
  const [active, setActive] = useState<StepId>("discover");
  const [auto, setAuto] = useState(true);
  const [selectedJob, setSelectedJob] = useState("Helio Systems");
  const [released, setReleased] = useState(false);

  useEffect(() => {
    if (!auto) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    const order: StepId[] = ["discover", "tailor", "approve", "track"];
    const interval = window.setInterval(() => {
      setActive((current) => {
        const idx = order.indexOf(current);
        return order[(idx + 1) % order.length];
      });
      setReleased(false);
    }, 5200);
    return () => window.clearInterval(interval);
  }, [auto]);

  const current = steps.find((s) => s.id === active)!;

  function go(id: StepId) {
    setAuto(false);
    setActive(id);
    setReleased(false);
  }

  return (
    <section
      id="demo"
      className="scroll-mt-24 border-y border-mkt-hairline bg-white py-16 sm:py-24"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl">
          <h2 className="text-balance text-3xl font-semibold tracking-[-0.03em] text-mkt-ink sm:text-4xl">
            See the workflow before you sign up
          </h2>
          <p className="mt-4 text-base leading-relaxed text-mkt-muted sm:text-lg">
            Four connected stages — discovery through pipeline. Interactive preview
            with sample data; every control either advances the demo or opens signup.
          </p>
        </div>

        <div className="mt-10 overflow-hidden rounded-2xl border border-mkt-hairline bg-mkt-canvas shadow-[0_32px_80px_-48px_rgba(12,18,34,0.45)]">
          <div className="flex flex-col border-b border-mkt-hairline lg:flex-row">
            <div
              className="flex gap-1 overflow-x-auto border-b border-mkt-hairline p-2 lg:w-56 lg:flex-col lg:border-b-0 lg:border-r lg:p-3"
              role="tablist"
              aria-label="Product workflow steps"
            >
              {steps.map((step) => {
                const Icon = step.icon;
                const selected = step.id === active;
                return (
                  <button
                    key={step.id}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    onClick={() => go(step.id)}
                    className={`flex min-w-[7.5rem] items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors ${
                      selected
                        ? "bg-white text-mkt-ink shadow-sm ring-1 ring-mkt-hairline"
                        : "text-mkt-muted hover:bg-white/70 hover:text-mkt-ink"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {step.label}
                  </button>
                );
              })}
            </div>

            <div className="flex-1 p-5 sm:p-8" role="tabpanel">
              <div className="mb-6 flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-mkt-indigo" />
                <div>
                  <h3 className="text-lg font-semibold text-mkt-ink">{current.title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-mkt-muted">
                    {current.body}
                  </p>
                </div>
              </div>
              <DemoPanel
                active={active}
                selectedJob={selectedJob}
                onSelectJob={(co) => {
                  setSelectedJob(co);
                  setAuto(false);
                  setActive("tailor");
                }}
                released={released}
                onRelease={() => {
                  if (active === "tailor") {
                    setActive("approve");
                    return;
                  }
                  setReleased(true);
                  setAuto(false);
                }}
              />
            </div>
          </div>

          <div className="flex flex-col gap-3 border-t border-mkt-hairline bg-white px-4 py-3 text-xs text-mkt-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <span>Interactive preview — sample data only</span>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setAuto((v) => !v)}
                className="rounded-full border border-mkt-hairline px-3 py-1.5 font-medium text-mkt-ink hover:bg-mkt-canvas-soft"
              >
                {auto ? "Pause tour" : "Resume tour"}
              </button>
              <Link
                href="/signup?from=demo"
                className="rounded-full bg-mkt-indigo px-3 py-1.5 font-semibold text-white hover:bg-mkt-indigo-deep"
              >
                Start free trial
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
