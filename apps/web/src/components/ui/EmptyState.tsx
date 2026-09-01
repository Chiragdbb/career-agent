"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";

type EmptyStateProps = {
  icon?: LucideIcon;
  title: string;
  description?: string;
  primaryActionLabel?: string;
  onPrimaryAction?: () => void;
  /** @deprecated Use primaryActionLabel + onPrimaryAction or href via actionLink */
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
        "flex flex-col items-center justify-center rounded-lg border border-border bg-card px-6 py-12 text-center",
        className,
      )}
    >
      {Icon ? (
        <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-muted">
          <Icon className="h-5 w-5 text-muted-foreground" />
        </div>
      ) : null}
      <p className="text-[15px] font-semibold text-foreground">{title}</p>
      {description ? (
        <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-muted-foreground">
          {description}
        </p>
      ) : null}
      {label ? (
        <div className="mt-4">
          {href ? (
            <Link href={href}>
              <Button>{label}</Button>
            </Link>
          ) : (
            <Button onClick={handleClick}>{label}</Button>
          )}
        </div>
      ) : null}
    </div>
  );
}
