import { Loader2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "gold" | "secondary" | "ghost" | "destructive";
type ButtonSize = "default" | "icon";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: LucideIcon;
};

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-primary-foreground border border-primary hover:brightness-105 active:scale-[0.98] disabled:opacity-50",
  gold:
    "bg-gold text-[#2B1C05] border border-gold font-semibold hover:brightness-105 active:scale-[0.98] disabled:opacity-50",
  secondary:
    "border border-line bg-transparent text-foreground hover:bg-paper-raised disabled:opacity-45",
  ghost:
    "border border-line bg-transparent text-foreground hover:bg-paper-raised disabled:opacity-45",
  destructive:
    "bg-destructive text-white hover:bg-destructive/90 disabled:opacity-60",
};

const sizeStyles: Record<ButtonSize, string> = {
  default: "px-4 py-2 text-[13.5px] font-medium gap-1.5",
  icon: "h-9 w-9 p-0",
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
        "inline-flex items-center justify-center rounded-lg transition-all duration-150",
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

/** Primary gold CTA matching reference GoldButton */
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
      variant="gold"
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

/** Secondary outlined button matching reference GhostButton */
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
