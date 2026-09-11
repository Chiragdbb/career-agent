import { cn } from "@/lib/cn";

type SoftBadgeProps = {
  children: React.ReactNode;
  className?: string;
  tone?: "lavender" | "coral" | "mint" | "peach" | "white";
};

const tones: Record<NonNullable<SoftBadgeProps["tone"]>, string> = {
  lavender: "bg-lavender text-lavender-deep",
  coral: "bg-coral-soft text-coral-deep",
  mint: "bg-teal-bg text-teal",
  peach: "bg-coral-bg text-coral-deep",
  white: "bg-white text-ink shadow-sm",
};

export function SoftBadge({
  children,
  className,
  tone = "lavender",
}: SoftBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
