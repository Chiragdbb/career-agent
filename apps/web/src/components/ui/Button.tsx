import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";
type ButtonSize = "default" | "icon";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 disabled:opacity-60",
  secondary:
    "border border-input bg-background text-foreground shadow-sm hover:bg-muted disabled:opacity-60",
  ghost: "text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60",
  destructive:
    "bg-destructive text-white hover:bg-destructive/90 disabled:opacity-60",
};

const sizeStyles: Record<ButtonSize, string> = {
  default: "px-4 py-2 text-sm font-medium",
  icon: "h-9 w-9 p-0",
};

export function Button({
  className,
  variant = "primary",
  size = "default",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md transition-colors",
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      {...props}
    />
  );
}
