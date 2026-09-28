"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CheckCircle2, Mail, Shield } from "lucide-react";

const jobs = [
  { co: "Helio Systems", role: "Senior Backend Engineer", score: 92, active: true },
  { co: "Northwind Labs", role: "Staff Platform Engineer", score: 88, active: false },
  { co: "Arcadia Health", role: "Engineering Lead", score: 84, active: false },
];

/**
 * High-fidelity product chrome mock for marketing hero.
 * All interactive controls either advance the local demo state or link to signup.
 */
export function HeroProductFrame() {
  const [step, setStep] = useState(0);
  const [released, setReleased] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    const id = window.setInterval(() => {
      setStep((s) => (s + 1) % 3);
      setReleased(false);
    }, 4800);
    return () => window.clearInterval(id);
  }, []);

  const panes = [
    {
      title: "Today",
      body: (
        <div className="space-y-2.5">
          {jobs.map((j, i) => (
            <button
              key={j.co}
              type="button"
              onClick={() => setStep(1)}
              className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left transition ${
                i === 0
                  ? "border-mkt-indigo/30 bg-mkt-indigo/5 shadow-sm"
                  : "border-mkt-hairline bg-white hover:bg-mkt-canvas-soft"
              }`}
            >
              <div>
                <p className="text-xs font-semibold text-mkt-ink">{j.co}</p>
                <p className="text-[11px] text-mkt-muted">{j.role}</p>
              </div>
              <span className="rounded-md bg-mkt-indigo/10 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-mkt-indigo">
                {j.score}
              </span>
            </button>
          ))}
        </div>
      ),
    },
    {
      title: "Approve",
      body: (
        <div className="space-y-3">
          <div className="rounded-xl border border-mkt-hairline bg-white p-3">
            <div className="flex items-start gap-2">
              <Mail className="mt-0.5 h-4 w-4 text-ember" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-mkt-ink">
                  Outreach to Maya Chen @ Helio
                </p>
                <p className="mt-0.5 text-[11px] text-mkt-muted">
                  Warm intro — awaiting your seal
                </p>
              </div>
            </div>
            {released ? (
              <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-[11px] font-medium text-emerald-700">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Marked released in this preview
              </div>
            ) : (
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <button
                  type="button"
                  onClick={() => setReleased(true)}
                  className="rounded-full bg-mkt-indigo px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-mkt-indigo-deep"
                >
                  Review &amp; release
                </button>
                <Link
                  href="/signup?from=hero-demo"
                  className="rounded-full border border-mkt-hairline px-3 py-1.5 text-center text-[11px] font-semibold text-mkt-ink hover:bg-mkt-canvas-soft"
                >
                  Do this for real →
                </Link>
              </div>
            )}
          </div>
          <p className="flex items-center gap-1.5 text-[11px] text-mkt-muted">
            <Shield className="h-3.5 w-3.5 text-mkt-indigo" />
            Nothing sends without your explicit approval
          </p>
        </div>
      ),
    },
    {
      title: "Pipeline",
      body: (
        <div className="grid grid-cols-4 gap-2">
          {[
            { label: "Applied", n: 6 },
            { label: "Screen", n: 2 },
            { label: "Interview", n: 1 },
            { label: "Offer", n: 0 },
          ].map((col) => (
            <Link
              key={col.label}
              href="/signup?from=pipeline"
              className="rounded-xl border border-mkt-hairline bg-mkt-canvas-soft p-2.5 text-center transition hover:border-mkt-indigo/30 hover:bg-white"
            >
              <p className="text-[10px] font-medium text-mkt-muted">{col.label}</p>
              <p className="mt-1 text-lg font-semibold tabular-nums text-mkt-ink">{col.n}</p>
            </Link>
          ))}
        </div>
      ),
    },
  ];

  return (
    <div className="relative mx-auto w-full max-w-xl lg:max-w-none">
      <div className="absolute -inset-3 rounded-[1.85rem] bg-[radial-gradient(circle_at_30%_20%,rgba(91,84,255,0.25),transparent_55%),radial-gradient(circle_at_90%_80%,rgba(232,93,76,0.12),transparent_50%)] blur-sm" />
      <div className="relative overflow-hidden rounded-2xl border border-mkt-hairline bg-white shadow-[0_40px_90px_-48px_rgba(7,11,20,0.55)]">
        <div className="flex items-center gap-2 border-b border-mkt-hairline bg-mkt-canvas-soft/80 px-4 py-2.5">
          <span className="size-2.5 rounded-full bg-[#ff5f57]" />
          <span className="size-2.5 rounded-full bg-[#febc2e]" />
          <span className="size-2.5 rounded-full bg-[#28c840]" />
          <span className="ml-2 text-[11px] font-medium text-mkt-muted">
            Waypoint · workspace preview
          </span>
        </div>
        <div className="grid sm:grid-cols-[140px_1fr]">
          <aside className="hidden border-r border-mkt-hairline bg-[#070b14] p-3 text-white sm:block">
            <p className="px-2 text-[10px] font-semibold uppercase tracking-wide text-white/40">
              Navigate
            </p>
            {["Today", "Opportunities", "Approvals", "Pipeline"].map((label, i) => (
              <button
                key={label}
                type="button"
                onClick={() => setStep(Math.min(i, 2))}
                className={`mt-1 flex w-full rounded-lg px-2 py-1.5 text-left text-[11px] font-medium transition ${
                  (step === 0 && i === 0) ||
                  (step === 1 && i === 2) ||
                  (step === 2 && i === 3)
                    ? "bg-white/10 text-white"
                    : "text-white/55 hover:bg-white/5 hover:text-white"
                }`}
              >
                {label}
              </button>
            ))}
          </aside>
          <div className="p-4 sm:p-5">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-mkt-ink">{panes[step].title}</h3>
              <div className="flex gap-1">
                {panes.map((_, i) => (
                  <button
                    key={i}
                    type="button"
                    aria-label={`Show ${panes[i].title}`}
                    onClick={() => {
                      setStep(i);
                      setReleased(false);
                    }}
                    className={`h-1.5 w-5 rounded-full transition ${
                      i === step ? "bg-mkt-indigo" : "bg-mkt-hairline hover:bg-mkt-muted/40"
                    }`}
                  />
                ))}
              </div>
            </div>
            {panes[step].body}
          </div>
        </div>
      </div>
    </div>
  );
}
