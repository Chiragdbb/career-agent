"use client";

import { cn } from "@/lib/cn";

type Tab<T extends string> = { id: T; label: string };

type SegmentedTabsProps<T extends string> = {
  tabs: Tab<T>[];
  active: T;
  onChange: (id: T) => void;
  className?: string;
  variant?: "pill" | "underline";
};

export function SegmentedTabs<T extends string>({
  tabs,
  active,
  onChange,
  className,
  variant = "pill",
}: SegmentedTabsProps<T>) {
  if (variant === "underline") {
    return (
      <div
        className={cn(
          "-mx-1 flex gap-1 overflow-x-auto pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible",
          className,
        )}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={cn(
              "shrink-0 rounded-full px-3.5 py-2 text-[13px] font-semibold transition-colors",
              active === tab.id
                ? "bg-lavender text-lavender-deep"
                : "text-text-muted hover:text-ink",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "-mx-1 overflow-x-auto pb-1 sm:mx-0 sm:overflow-visible",
        className,
      )}
    >
      <div className="inline-flex min-w-full gap-1 rounded-full bg-muted p-1 sm:min-w-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={cn(
              "shrink-0 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors",
              active === tab.id
                ? "bg-white text-ink shadow-sm"
                : "text-text-muted hover:text-ink",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
