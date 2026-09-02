import Link from "next/link";
import { Sparkles } from "lucide-react";

import { GoldButton, GhostButton } from "@/components/ui/Button";
import { TrailMark } from "@/components/ui/Illustrations";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-paper">
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-4 sm:px-8 md:px-12">
        <div className="flex min-w-0 items-center gap-2.5">
          <TrailMark size={32} />
          <span className="truncate font-serif text-[15px] font-semibold text-ink">
            Waypoint
          </span>
        </div>
        <nav className="hidden items-center gap-6 text-sm text-text-muted lg:flex lg:gap-8">
          <a href="#features" className="hover:text-ink">
            Features
          </a>
          <a href="#how-it-works" className="hover:text-ink">
            How it works
          </a>
          <Link href="/login" className="hover:text-ink">
            Pricing
          </Link>
          <Link href="/signup" className="hover:text-ink">
            Get started
          </Link>
        </nav>
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
          <Link href="/login" className="hidden sm:block">
            <GhostButton className="px-2 sm:px-4">Sign in</GhostButton>
          </Link>
          <Link href="/signup">
            <GoldButton className="px-3 text-xs sm:px-4 sm:text-sm">Start free</GoldButton>
          </Link>
        </div>
      </header>

      <section className="flex flex-col items-center gap-10 px-4 py-12 sm:px-8 sm:py-16 lg:flex-row lg:items-center lg:gap-12 lg:px-12 lg:py-16">
        <div className="flex w-full max-w-xl flex-col gap-5 sm:gap-6">
          <div className="inline-flex w-fit items-center gap-1.5 rounded-full border border-teal/30 bg-teal-bg px-3 py-1.5">
            <Sparkles className="h-3 w-3 text-teal" />
            <span className="text-xs font-medium text-teal">
              AI-powered career workspace
            </span>
          </div>
          <h1 className="font-serif text-4xl leading-[1.08] text-ink sm:text-5xl">
            Your job search, finally organized.
          </h1>
          <p className="text-base leading-relaxed text-text-muted sm:text-[17px]">
            Career Agent connects jobs, applications, contacts, and outreach into
            one intelligent system — so you always know what to do next.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <Link href="/signup" className="w-full sm:w-auto">
              <GoldButton className="w-full px-6 py-2.5 sm:w-auto">Start free trial</GoldButton>
            </Link>
            <Link href="/login" className="w-full sm:w-auto">
              <GhostButton className="w-full sm:w-auto">See how it works</GhostButton>
            </Link>
          </div>
          <p className="text-xs text-text-faint">
            Free for 14 days · No credit card · Cancel anytime
          </p>
        </div>

        <div className="w-full max-w-xl overflow-hidden rounded-xl border border-line bg-paper-raised shadow-[0_8px_32px_rgba(22,35,31,0.1)]">
          <div className="flex items-center gap-1.5 border-b border-line bg-ink px-4 py-3">
            <div className="h-2.5 w-2.5 rounded-full bg-brick/80" />
            <div className="h-2.5 w-2.5 rounded-full bg-gold/80" />
            <div className="h-2.5 w-2.5 rounded-full bg-teal/80" />
          </div>
          <div className="flex min-h-[16rem] items-center justify-center p-6 sm:h-72 sm:p-8">
            <div className="text-center">
              <p className="font-serif text-xl text-ink sm:text-2xl">
                Good morning, Chirag
              </p>
              <p className="mt-2 text-sm text-text-muted">
                12 applications · 3 interviews · 5 follow-ups
              </p>
              <div className="mt-6 grid grid-cols-1 gap-3 text-left sm:grid-cols-2">
                {["Applications ready", "Follow-ups due", "New jobs", "Interview prep"].map(
                  (item) => (
                    <div
                      key={item}
                      className="rounded-md border border-line bg-paper px-3 py-2 text-xs text-text-muted"
                    >
                      {item}
                    </div>
                  ),
                )}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
