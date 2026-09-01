"use client";

import Link from "next/link";
import { CheckCircle2, Circle } from "lucide-react";

import { Card, CardTitle } from "@/components/ui/Card";

type OnboardingStep = {
  id: string;
  label: string;
  href: string;
  complete: boolean;
};

type OnboardingChecklistProps = {
  steps: OnboardingStep[];
};

export function OnboardingChecklist({ steps }: OnboardingChecklistProps) {
  const incomplete = steps.filter((step) => !step.complete);
  if (incomplete.length === 0) return null;

  return (
    <Card className="mb-6">
      <CardTitle>Get started</CardTitle>
      <p className="mt-1 text-sm text-muted-foreground">
        Complete these steps to unlock job discovery and applications.
      </p>
      <ul className="mt-4 space-y-3">
        {steps.map((step) => (
          <li key={step.id}>
            <Link
              href={step.href}
              className="flex items-center gap-3 rounded-md border border-border px-3 py-2.5 transition-colors hover:bg-muted/40"
            >
              {step.complete ? (
                <CheckCircle2 className="h-5 w-5 shrink-0 text-primary" aria-hidden />
              ) : (
                <Circle className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
              )}
              <span
                className={
                  step.complete
                    ? "text-sm text-muted-foreground line-through"
                    : "text-sm font-medium text-foreground"
                }
              >
                {step.label}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
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
