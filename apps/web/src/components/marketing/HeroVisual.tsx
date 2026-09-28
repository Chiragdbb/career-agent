"use client";

import { Sparkles } from "lucide-react";

import { CareerOrbitCanvas } from "@/components/marketing/CareerOrbitCanvas";

export function HeroVisual() {
  return (
    <div className="relative mx-auto aspect-[4/3] w-full max-w-xl lg:max-w-none">
      <div className="absolute inset-0 rounded-[1.75rem] border border-mkt-hairline bg-white/70 shadow-[0_40px_90px_-50px_rgba(12,18,34,0.55)] backdrop-blur-sm" />
      <CareerOrbitCanvas />
      <div className="pointer-events-none absolute inset-x-6 bottom-6 rounded-2xl border border-mkt-hairline/80 bg-white/90 p-4 shadow-[0_20px_50px_-30px_rgba(12,18,34,0.35)] sm:inset-x-8">
        <div className="flex items-center gap-2 text-xs font-medium text-mkt-muted">
          <Sparkles className="h-3.5 w-3.5 text-mkt-indigo" />
          Live pipeline snapshot
        </div>
        <p className="mt-2 text-sm font-semibold text-mkt-ink">
          3 drafts waiting for your seal
        </p>
        <p className="mt-1 text-xs text-mkt-muted">
          Illustrative hero panel — connect sources to populate yours.
        </p>
      </div>
    </div>
  );
}
