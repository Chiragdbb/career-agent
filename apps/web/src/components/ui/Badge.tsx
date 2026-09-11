import { cn } from "@/lib/cn";

type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "error"
  | "primary"
  | "lavender"
  | "mint"
  | "peach";

type BadgeProps = {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
};

const variantStyles: Record<BadgeVariant, string> = {
  default: "border-line bg-white text-ink",
  success: "border-transparent bg-success-subtle text-success",
  warning: "border-transparent bg-warning-subtle text-warning",
  error: "border-transparent bg-error-subtle text-error",
  primary: "border-transparent bg-coral-soft text-coral-deep",
  lavender: "border-transparent bg-lavender text-lavender-deep",
  mint: "border-transparent bg-teal-bg text-teal",
  peach: "border-transparent bg-coral-bg text-coral-deep",
};

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide",
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
