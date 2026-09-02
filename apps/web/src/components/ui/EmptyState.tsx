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
        "flex flex-col items-center px-6 py-10 text-center",
        className,
      )}
    >
      {Icon ? (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-line-soft">
          <Icon className="h-5 w-5 text-text-muted" />
        </div>
      ) : (
        <EmptyDoodle />
      )}
      <p className="mt-3 font-serif text-[17px] text-ink">{title}</p>
      {description ? (
        <p className="mt-2 max-w-[280px] text-[13.5px] leading-relaxed text-text-muted">
          {description}
        </p>
      ) : null}
      {label ? (
        <div className="mt-4">
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
