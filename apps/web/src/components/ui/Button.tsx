import { Loader2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "gold" | "secondary" | "ghost" | "destructive";
type ButtonSize = "default" | "icon" | "lg";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: LucideIcon;
};

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-coral text-white border border-coral hover:bg-coral-deep active:scale-[0.98] disabled:opacity-50",
  gold:
    "bg-coral text-white border border-coral font-semibold hover:bg-coral-deep active:scale-[0.98] disabled:opacity-50",
  secondary:
    "border border-line bg-white text-ink hover:bg-paper disabled:opacity-45",
  ghost:
    "border border-line bg-transparent text-ink hover:bg-white/80 disabled:opacity-45",
  destructive:
    "bg-coral-deep text-white hover:brightness-95 disabled:opacity-60",
};

const sizeStyles: Record<ButtonSize, string> = {
  default: "rounded-full px-5 py-2.5 text-[13.5px] font-semibold gap-1.5",
  lg: "rounded-full px-6 py-3 text-sm font-semibold gap-2",
  icon: "h-10 w-10 rounded-full p-0",
};

export function Button({
  className,
  variant = "primary",
  size = "default",
  loading,
  icon: Icon,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center transition-all duration-150",
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : Icon ? (
        <Icon className="h-3.5 w-3.5" />
      ) : null}
      {children}
    </button>
  );
}

/** Primary CTA — coral (kept as GoldButton for call-site compatibility) */
export function GoldButton({
  className,
  loading,
  icon: Icon,
  children,
  disabled,
  ...props
}: Omit<ButtonProps, "variant">) {
  return (
    <Button
      variant="primary"
      className={className}
      loading={loading}
      icon={Icon}
      disabled={disabled}
      {...props}
    >
      {children}
    </Button>
  );
}

export function GhostButton({
  className,
  loading,
  icon: Icon,
  children,
  disabled,
  ...props
}: Omit<ButtonProps, "variant">) {
  return (
    <Button
      variant="ghost"
      className={className}
      loading={loading}
      icon={Icon}
      disabled={disabled}
      {...props}
    >
      {children}
    </Button>
  );
}
