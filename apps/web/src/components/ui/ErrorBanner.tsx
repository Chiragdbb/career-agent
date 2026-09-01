"use client";

import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";

type ErrorBannerProps = {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
};

export function ErrorBanner({
  message,
  onRetry,
  retryLabel = "Retry",
  className,
}: ErrorBannerProps) {
  return (
    <div
      className={cn(
        "mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3",
        className,
      )}
      role="alert"
    >
      <p className="text-sm text-destructive">{message}</p>
      {onRetry ? (
        <Button variant="secondary" className="px-3 py-1.5 text-xs" onClick={onRetry}>
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}
