import { cn } from "@/lib/cn";

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
};

export function Input({ label, className, id, ...props }: InputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");

  if (label) {
    return (
      <label htmlFor={inputId} className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium text-ink">{label}</span>
        <input
          id={inputId}
          className={cn(
            "rounded-full border border-input bg-white px-4 py-2.5 text-sm shadow-sm",
            "placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-coral/25",
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
        "rounded-full border border-input bg-white px-4 py-2.5 text-sm shadow-sm",
        "placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-coral/25",
        className,
      )}
      {...props}
    />
  );
}
