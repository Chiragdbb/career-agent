import { cn } from "@/lib/cn";

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
};

export function Input({ label, className, id, ...props }: InputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");

  if (label) {
    return (
      <label htmlFor={inputId} className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium text-foreground">{label}</span>
        <input
          id={inputId}
          className={cn(
            "rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
            "placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/30",
            className,
          )}
          {...props}
        />
      </label>
    );
  }

  return (
    <input
      id={inputId}
      className={cn(
        "rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
        "placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/30",
        className,
      )}
      {...props}
    />
  );
}
