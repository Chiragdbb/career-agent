"use client";

import Link from "next/link";
import { Check } from "lucide-react";

import { OnboardingIllustration } from "@/components/ui/Illustrations";
import { cn } from "@/lib/cn";

type OnboardingStep = {
  id: string;
  label: string;
  href: string;
  complete: boolean;
};

type OnboardingChecklistProps = {
  steps: OnboardingStep[];
  className?: string;
};

export function OnboardingChecklist({ steps, className }: OnboardingChecklistProps) {
  const doneCount = steps.filter((s) => s.complete).length;
  if (doneCount === steps.length) return null;

  return (
    <div
      className={cn(
        "mb-5 flex animate-riseIn items-center justify-between gap-6 rounded-[14px] bg-ink-soft px-6 py-5",
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="mb-3.5 flex items-baseline gap-2.5">
          <span className="font-serif text-[19px] font-semibold text-[#F3EFE2]">
            Let&apos;s set up your search
          </span>
          <span className="text-xs text-gold-soft">
            {doneCount} of {steps.length} done
          </span>
        </div>
        <ul className="flex flex-col gap-2">
          {steps.map((step) => (
            <li key={step.id}>
              <Link
                href={step.href}
                className="flex items-center gap-2.5 py-0.5 text-left"
              >
                <span
                  className={cn(
                    "flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[5px] border-[1.5px] transition-all duration-200",
                    step.complete
                      ? "border-gold bg-gold"
                      : "border-[#4A5C51] bg-transparent",
                  )}
                >
                  {step.complete ? (
                    <Check className="h-3 w-3 text-[#2B1C05]" strokeWidth={3} />
                  ) : null}
                </span>
                <span
                  className={cn(
                    "text-[13.5px]",
                    step.complete
                      ? "text-[#8A968E] line-through"
                      : "text-[#E4E0D2]",
                  )}
                >
                  {step.label}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
      <div className="hidden shrink-0 opacity-90 sm:block">
        <OnboardingIllustration />
      </div>
    </div>
  );
}

export function preferencesUnset(settings: {
  target_roles?: string[];
  locations?: string[];
}): boolean {
  const roles = settings.target_roles ?? [];
  const locations = settings.locations ?? [];
  return roles.length === 0 && locations.length === 0;
}
