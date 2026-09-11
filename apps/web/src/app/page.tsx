import Link from "next/link";
import { Sparkles } from "lucide-react";

import { GoldButton, GhostButton } from "@/components/ui/Button";
import { SoftBadge } from "@/components/ui/SoftBadge";
import { TrailMark } from "@/components/ui/Illustrations";
import { SiteFooter } from "@/components/SiteFooter";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <header className="flex items-center justify-between gap-3 border-b border-line/80 bg-white/80 px-4 py-4 backdrop-blur sm:px-8 md:px-12">
        <div className="flex min-w-0 items-center gap-2.5">
          <TrailMark size={32} />
          <span className="truncate text-[15px] font-bold tracking-tight text-ink">
            Waypoint
          </span>
        </div>
        <nav className="hidden items-center gap-6 text-sm font-medium text-text-muted lg:flex lg:gap-8">
          <a href="#features" className="hover:text-ink">
            Features
          </a>
          <a href="#how-it-works" className="hover:text-ink">
            How it works
          </a>
          <Link href="/signup" className="hover:text-ink">
            Get started
          </Link>
        </nav>
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
          <Link href="/login" className="hidden sm:block">
            <GhostButton className="px-2 sm:px-4">Sign in</GhostButton>
          </Link>
          <Link href="/signup">
            <GoldButton className="px-3 text-xs sm:px-4 sm:text-sm">
              Start free
            </GoldButton>
          </Link>
        </div>
      </header>

      <section className="mx-auto grid w-full max-w-[1200px] gap-10 px-4 py-12 sm:px-8 sm:py-16 lg:grid-cols-2 lg:items-center lg:gap-12 lg:px-12 lg:py-20">
        <div className="flex flex-col gap-5 sm:gap-6">
          <SoftBadge tone="lavender" className="w-fit">
            <Sparkles className="h-3 w-3" />
            Thoughtful career intelligence
          </SoftBadge>
          <h1 className="text-4xl font-bold leading-[1.08] tracking-tight text-ink sm:text-5xl">
            Your job search,{" "}
            <span className="font-serif italic text-coral">finally calm.</span>
          </h1>
          <p className="text-base leading-relaxed text-text-muted sm:text-[17px]">
            Waypoint connects jobs, applications, contacts, and outreach — with
            human approval before anything leaves your desk.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <Link href="/signup" className="w-full sm:w-auto">
              <GoldButton className="w-full px-6 py-2.5 sm:w-auto">
                Start free trial
              </GoldButton>
            </Link>
            <Link href="/login" className="w-full sm:w-auto">
              <GhostButton className="w-full sm:w-auto">Sign in</GhostButton>
            </Link>
          </div>
          <p className="text-xs text-text-faint">
            Free for 14 days · No credit card · Cancel anytime
          </p>
        </div>

        <div
          className="overflow-hidden rounded-3xl border border-line bg-white p-6 shadow-card sm:p-8"
          style={{
            backgroundImage:
              "linear-gradient(158.78deg, rgb(249, 241, 255) 0%, rgb(255, 255, 255) 55%, rgba(226, 223, 255, 0.35) 100%)",
          }}
        >
          <SoftBadge tone="white" className="mb-4 shadow-sm">
            <span className="size-2 rounded-full bg-coral" />
            Today&apos;s momentum
          </SoftBadge>
          <p className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">
            Good morning.
            <span className="mt-1 block text-coral">You&apos;ve got momentum.</span>
          </p>
          <p className="mt-3 text-sm text-text-muted">
            Approvals, opportunities, and conversations — ready when you are.
          </p>
          <div className="mt-6 grid grid-cols-1 gap-3 text-left sm:grid-cols-2">
            {[
              "Ready for your seal",
              "Curated opportunities",
              "Warm outreach drafts",
              "Interview cockpit",
            ].map((item) => (
              <div
                key={item}
                className="rounded-2xl border border-line bg-white/80 px-3 py-3 text-xs font-semibold text-text-muted shadow-sm"
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto w-full max-w-[1200px] px-4 pb-16 sm:px-8 md:px-12">
        <h2 className="text-2xl font-bold tracking-tight text-ink">Built for intentional careers</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          {[
            {
              title: "Human control",
              body: "Nothing is submitted or sent without your explicit approval.",
            },
            {
              title: "Truthful drafts",
              body: "No invented experience, employers, or metrics — ever.",
            },
            {
              title: "One trajectory",
              body: "Jobs, applications, outreach, and interviews in one calm workspace.",
            },
          ].map((f) => (
            <div
              key={f.title}
              className="rounded-3xl border border-line bg-white p-5 shadow-soft"
            >
              <h3 className="font-bold text-ink">{f.title}</h3>
              <p className="mt-2 text-sm text-text-muted">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <div id="how-it-works" />
      <SiteFooter />
    </div>
  );
}
