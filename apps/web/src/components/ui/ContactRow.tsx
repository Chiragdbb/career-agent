import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";

type ContactRowProps = {
  id: string;
  name: string;
  subtitle?: string;
  status: string;
  initials?: string;
  className?: string;
};

export function ContactRow({
  id,
  name,
  subtitle,
  status,
  initials,
  className,
}: ContactRowProps) {
  const letters =
    initials ||
    name
      .split(" ")
      .filter(Boolean)
      .map((p) => p[0])
      .join("")
      .slice(0, 2)
      .toUpperCase() ||
    "?";

  return (
    <Link
      href={`/contacts/${id}`}
      className={cn(
        "flex items-center gap-3 border-b border-line px-4 py-3.5 transition-colors last:border-0 hover:bg-paper",
        className,
      )}
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-lavender text-xs font-semibold text-lavender-deep">
        {letters}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{name}</p>
        {subtitle ? (
          <p className="truncate text-xs text-text-muted">{subtitle}</p>
        ) : null}
      </div>
      <Badge variant="default" className="shrink-0 capitalize">
        {status}
      </Badge>
      <ChevronRight className="h-4 w-4 shrink-0 text-text-faint" />
    </Link>
  );
}
