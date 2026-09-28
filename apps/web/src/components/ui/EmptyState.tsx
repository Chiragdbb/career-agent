"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { GoldButton } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

type EmptyStateProps = {
  icon?: LucideIcon;
  title: string;
  description?: string;
  primaryActionLabel?: string;
  onPrimaryAction?: () => void;
  /** @deprecated Use primaryActionLabel + onPrimaryAction or actionHref */
  action?: { label: string; href?: string; onClick?: () => void };
  actionHref?: string;
  className?: string;
};

export function EmptyState({
  icon: Icon,
  title,
  description,
  primaryActionLabel,
  onPrimaryAction,
  action,
  actionHref,
  className,
}: EmptyStateProps) {
  const label = primaryActionLabel ?? action?.label;
  const href = actionHref ?? action?.href;
  const handleClick = onPrimaryAction ?? action?.onClick;
  const hasAction = Boolean(label && (href || handleClick));

  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-2xl border border-line bg-white px-6 py-14 text-center shadow-soft",
        className,
      )}
    >
      {Icon ? (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-lavender text-lavender-deep">
          <Icon className="h-5 w-5" />
        </div>
      ) : (
        <div className="mb-4 h-12 w-12 rounded-2xl bg-gradient-to-br from-coral/25 to-[#22d3ee]/15" />
      )}
      <p className="text-[17px] font-semibold tracking-tight text-ink">{title}</p>
      {description ? (
        <p className="mt-2 max-w-[340px] text-[13.5px] leading-relaxed text-text-muted">
          {description}
        </p>
      ) : null}
      {hasAction ? (
        <div className="mt-6">
          {href ? (
            <Link href={href}>
              <GoldButton>{label}</GoldButton>
            </Link>
          ) : (
            <GoldButton onClick={handleClick}>{label}</GoldButton>
          )}
        </div>
      ) : null}
    </div>
  );
}
