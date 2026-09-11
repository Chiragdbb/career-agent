import { cn } from "@/lib/cn";

type DiffPaneProps = {
  leftLabel: string;
  rightLabel: string;
  left: React.ReactNode;
  right: React.ReactNode;
  className?: string;
};

export function DiffPane({
  leftLabel,
  rightLabel,
  left,
  right,
  className,
}: DiffPaneProps) {
  return (
    <div
      className={cn(
        "grid gap-3 rounded-2xl border border-line bg-paper/60 p-3 sm:grid-cols-2 sm:p-4",
        className,
      )}
    >
      <div className="rounded-xl bg-white p-3 shadow-sm">
        <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-text-faint">
          {leftLabel}
        </p>
        <div className="text-sm leading-relaxed text-text-muted">{left}</div>
      </div>
      <div className="rounded-xl border border-coral/20 bg-coral-bg/50 p-3 shadow-sm">
        <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-coral-deep">
          {rightLabel}
        </p>
        <div className="text-sm leading-relaxed text-ink">{right}</div>
      </div>
    </div>
  );
}
