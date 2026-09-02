"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Chip } from "@/components/ui/Chip";
import { cn } from "@/lib/cn";

type CollapsibleSectionProps = {
  title: string;
  tone?: "good" | "warn" | "neutral" | "gold";
  chips: string[];
  defaultOpen?: boolean;
  className?: string;
};

export function CollapsibleSection({
  title,
  tone = "neutral",
  chips,
  defaultOpen = false,
  className,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={cn("overflow-hidden rounded-[10px] border border-line-soft", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between bg-paper-raised px-4 py-3"
      >
        <span className="text-[13.5px] font-semibold text-ink">{title}</span>
        {open ? (
          <ChevronUp className="h-4 w-4 text-text-muted" />
        ) : (
          <ChevronDown className="h-4 w-4 text-text-muted" />
        )}
      </button>
      <div
        className={cn(
          "overflow-hidden bg-paper transition-[max-height] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
          open ? "max-h-52" : "max-h-0",
        )}
      >
        <div className="flex flex-wrap gap-1.5 px-4 py-3">
          {chips.map((c) => (
            <Chip key={c} tone={tone}>
              {c}
            </Chip>
          ))}
        </div>
      </div>
    </div>
  );
}
