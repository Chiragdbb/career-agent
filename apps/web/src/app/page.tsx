import Link from "next/link";
import {
  ArrowRight,
  GitBranch,
  Lock,
  Radar,
  Shield,
  Workflow,
} from "lucide-react";

import { HeroProductFrame } from "@/components/marketing/HeroProductFrame";
import { MarketingHeader } from "@/components/marketing/MarketingHeader";
import { ProductDemo } from "@/components/marketing/ProductDemo";
import { SiteFooter } from "@/components/SiteFooter";

export default function HomePage() {
  return (
    <div className="marketing-shell relative flex min-h-screen flex-col bg-mkt-canvas text-mkt-ink">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[70vh] aurora-mesh opacity-90" />

      <MarketingHeader />

      <main className="relative flex-1">
        <section className="mx-auto grid max-w-6xl gap-12 px-4 pb-16 pt-10 sm:px-6 sm:pb-20 sm:pt-14 lg:grid-cols-[1.02fr_0.98fr] lg:items-center lg:gap-12 lg:px-8 lg:pb-28 lg:pt-16">
          <div className="flex animate-riseIn flex-col gap-6 sm:gap-7">
            <p className="text-sm font-medium text-mkt-indigo">Waypoint</p>
            <h1 className="max-w-xl text-balance text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-mkt-ink sm:text-5xl lg:text-[3.4rem]">
              The career command center that never sends without{" "}
              <span className="font-serif italic font-medium text-mkt-indigo">
                your seal.
              </span>
            </h1>
            <p className="max-w-lg text-base leading-relaxed text-mkt-muted sm:text-lg">
              Discover roles, tailor truthful materials, draft outreach, and run the
              full pipeline — with human approval wired into every outbound action.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Link
                href="/signup"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-mkt-indigo px-6 py-3 text-sm font-semibold text-white shadow-glow transition hover:-translate-y-0.5 hover:bg-mkt-indigo-deep"
              >
                Start free trial
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="#demo"
                className="inline-flex items-center justify-center rounded-full border border-mkt-hairline bg-white px-6 py-3 text-sm font-semibold text-mkt-ink transition hover:bg-mkt-canvas-soft"
              >
                See how it works
              </a>
            </div>
            <p className="text-xs text-mkt-muted">
              14-day trial · No credit card · Cancel anytime
            </p>
          </div>

          <div className="animate-riseIn [animation-delay:120ms]">
            <HeroProductFrame />
          </div>
        </section>

        <section className="border-y border-mkt-hairline bg-white/70 py-8">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-10 gap-y-4 px-4 text-sm font-medium text-mkt-muted sm:px-6 lg:px-8">
            {[
              { icon: Shield, label: "Human approval gates" },
              { icon: Lock, label: "No fabricated experience" },
              { icon: GitBranch, label: "Full audit trail" },
              { icon: Radar, label: "Source-backed discovery" },
            ].map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-mkt-indigo" />
                {label}
              </div>
            ))}
          </div>
        </section>

        <ProductDemo />

        <section id="features" className="scroll-mt-24 py-16 sm:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
            <div className="max-w-2xl">
              <h2 className="text-balance text-3xl font-semibold tracking-[-0.03em] text-mkt-ink sm:text-4xl">
                Infrastructure for intentional careers
              </h2>
              <p className="mt-4 text-base leading-relaxed text-mkt-muted sm:text-lg">
                One workspace that connects discovery, documents, applications, and
                conversations — without sacrificing control.
              </p>
            </div>

            <div className="mt-10 grid gap-4 lg:grid-cols-12">
              <article className="rounded-2xl border border-mkt-hairline bg-white p-6 shadow-card lg:col-span-7 lg:p-8">
                <Radar className="h-6 w-6 text-mkt-indigo" />
                <h3 className="mt-4 text-xl font-semibold tracking-[-0.02em] text-mkt-ink">
                  Discovery that respects your filters
                </h3>
                <p className="mt-3 max-w-prose text-sm leading-relaxed text-mkt-muted sm:text-base">
                  Ingest from configured sources, dedupe listings, and score fit against
                  the profile you maintain — with every ingestion logged for review.
                </p>
                <Link
                  href="/signup?from=features-discover"
                  className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-mkt-indigo hover:underline"
                >
                  Set up discovery
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </article>

              <div className="grid gap-4 lg:col-span-5">
                <article className="rounded-2xl border border-mkt-hairline bg-mkt-canvas-soft p-6">
                  <Lock className="h-6 w-6 text-ember" />
                  <h3 className="mt-4 text-lg font-semibold text-mkt-ink">
                    Human-in-the-loop by default
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-mkt-muted">
                    Submissions and outbound email require explicit release — or a rule
                    you defined ahead of time.
                  </p>
                  <Link
                    href="/signup?from=features-approve"
                    className="mt-4 inline-flex text-sm font-semibold text-mkt-indigo hover:underline"
                  >
                    See approvals →
                  </Link>
                </article>
                <article className="rounded-2xl border border-mkt-hairline bg-white p-6">
                  <GitBranch className="h-6 w-6 text-emerald-600" />
                  <h3 className="mt-4 text-lg font-semibold text-mkt-ink">
                    Versioned documents
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-mkt-muted">
                    Résumé and letter variants stay tied to employers and postings, with
                    diffs you can inspect before sending.
                  </p>
                  <Link
                    href="/signup?from=features-docs"
                    className="mt-4 inline-flex text-sm font-semibold text-mkt-indigo hover:underline"
                  >
                    Manage documents →
                  </Link>
                </article>
              </div>
            </div>
          </div>
        </section>

        <section className="border-y border-white/10 aurora-mesh-dark py-16 text-white sm:py-24">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 sm:px-6 lg:grid-cols-2 lg:items-center lg:px-8">
            <div>
              <h2 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">
                One cockpit for the whole search
              </h2>
              <p className="mt-4 text-base leading-relaxed text-white/70">
                Approvals, opportunities, conversations, and interviews stay connected
                to the same job record — searchable and auditable.
              </p>
              <ul className="mt-6 space-y-3 text-sm text-white/80">
                <li className="flex gap-2">
                  <span className="text-mkt-indigo">—</span>
                  Ranked opportunities with company context
                </li>
                <li className="flex gap-2">
                  <span className="text-mkt-indigo">—</span>
                  Drafts that wait for your seal
                </li>
                <li className="flex gap-2">
                  <span className="text-mkt-indigo">—</span>
                  Interview prep linked to each application
                </li>
              </ul>
              <Link
                href="/signup"
                className="mt-8 inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-mkt-ink hover:bg-white/90"
              >
                Create your workspace
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/5 p-2 shadow-2xl backdrop-blur">
              <HeroProductFrame />
            </div>
          </div>
        </section>

        <section id="how-it-works" className="scroll-mt-24 bg-white py-16 sm:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
            <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
              <div>
                <h2 className="text-3xl font-semibold tracking-[-0.03em] text-mkt-ink sm:text-4xl">
                  How you operate Waypoint
                </h2>
                <p className="mt-4 text-base leading-relaxed text-mkt-muted">
                  A weekly rhythm that keeps momentum without burning trust.
                </p>
              </div>
              <ol className="space-y-4">
                {[
                  {
                    title: "Connect sources & preferences",
                    body: "Point Waypoint at boards and criteria. Set location, level, and compensation once.",
                    href: "/signup?next=/preferences",
                  },
                  {
                    title: "Review ranked opportunities",
                    body: "Triage new roles, archive mismatches, and promote strong fits into applications.",
                    href: "/signup?next=/jobs",
                  },
                  {
                    title: "Approve drafts, then track outcomes",
                    body: "Release tailored packets when they read like you. Follow interviews from the same record.",
                    href: "/signup?next=/approvals",
                  },
                ].map((step, i) => (
                  <li key={step.title}>
                    <Link
                      href={step.href}
                      className="block rounded-2xl border border-mkt-hairline bg-mkt-canvas-soft p-5 transition hover:border-mkt-indigo/30 hover:bg-white hover:shadow-soft sm:p-6"
                    >
                      <div className="flex gap-3">
                        <Workflow className="mt-0.5 h-4 w-4 shrink-0 text-mkt-indigo" />
                        <div>
                          <h3 className="text-base font-semibold text-mkt-ink">
                            <span className="mr-2 tabular-nums text-mkt-muted">
                              {i + 1}.
                            </span>
                            {step.title}
                          </h3>
                          <p className="mt-2 text-sm leading-relaxed text-mkt-muted">
                            {step.body}
                          </p>
                        </div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        <section id="pricing" className="scroll-mt-24 py-16 sm:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
            <div className="overflow-hidden rounded-3xl border border-mkt-hairline bg-[linear-gradient(135deg,#ffffff_0%,#f4f7fb_45%,#eeedff_100%)] p-8 sm:p-12 lg:flex lg:items-center lg:justify-between lg:gap-12">
              <div className="max-w-xl">
                <h2 className="text-3xl font-semibold tracking-[-0.03em] text-mkt-ink sm:text-4xl">
                  Start free. Scale when the search gets serious.
                </h2>
                <p className="mt-4 text-base leading-relaxed text-mkt-muted">
                  Every account begins on a 14-day trial with full workflow access.
                  Upgrade later when you need higher volume or automation rules.
                </p>
              </div>
              <div className="mt-8 flex shrink-0 flex-col gap-3 sm:flex-row lg:mt-0 lg:flex-col">
                <Link
                  href="/signup"
                  className="inline-flex items-center justify-center rounded-full bg-mkt-ink px-8 py-3.5 text-sm font-semibold text-white hover:bg-[#151d33]"
                >
                  Create your workspace
                </Link>
                <Link
                  href="/login"
                  className="inline-flex items-center justify-center rounded-full border border-mkt-hairline bg-white px-8 py-3.5 text-sm font-semibold text-mkt-ink hover:bg-mkt-canvas-soft"
                >
                  Sign in
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter variant="marketing" />
    </div>
  );
}
