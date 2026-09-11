"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { GoldButton } from "@/components/ui/Button";
import { EmptyDoodle } from "@/components/ui/Illustrations";
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

  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-3xl border border-line bg-white px-6 py-12 text-center shadow-soft",
        className,
      )}
    >
      {Icon ? (
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-lavender">
          <Icon className="h-5 w-5 text-lavender-deep" />
        </div>
      ) : (
        <EmptyDoodle />
      )}
      <p className="mt-3 text-[17px] font-bold tracking-tight text-ink">{title}</p>
      {description ? (
        <p className="mt-2 max-w-[320px] text-[13.5px] leading-relaxed text-text-muted">
          {description}
        </p>
      ) : null}
      {label ? (
        <div className="mt-5">
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
