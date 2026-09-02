import { cn } from "@/lib/cn";

type ChipTone = "neutral" | "good" | "warn" | "gold";

type ChipProps = {
  children: React.ReactNode;
  tone?: ChipTone;
  className?: string;
};

const toneStyles: Record<ChipTone, string> = {
  neutral: "bg-paper text-text-muted border-line/30",
  good: "bg-teal-bg text-teal border-teal/20",
  warn: "bg-brick-bg text-brick border-brick/20",
  gold: "bg-gold-bg text-[#7A551D] border-gold/20",
};

export function Chip({ children, tone = "neutral", className }: ChipProps) {
  return (
    <span
      className={cn(
        "inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-[12.5px]",
        toneStyles[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
