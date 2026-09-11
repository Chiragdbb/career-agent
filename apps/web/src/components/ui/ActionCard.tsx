import { cn } from "@/lib/cn";

type ActionCardProps = {
  children: React.ReactNode;
  className?: string;
  highlight?: boolean;
};

export function ActionCard({ children, className, highlight }: ActionCardProps) {
  return (
    <div
      className={cn(
        "flex h-full flex-col rounded-3xl border bg-white p-6 shadow-soft sm:p-8",
        highlight ? "border-coral/30 bg-coral-bg/40" : "border-line",
        className,
      )}
    >
      {children}
    </div>
  );
}
