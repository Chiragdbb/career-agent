import { cn } from "@/lib/cn";

type MetricCardProps = {
  label: string;
  value: number | string;
  change?: string;
  changeVariant?: "success" | "warning" | "muted";
  className?: string;
};

export function MetricCard({
  label,
  value,
  change,
  changeVariant = "success",
  className,
}: MetricCardProps) {
  const changeColors = {
    success: "text-primary",
    warning: "text-warning",
    muted: "text-muted-foreground",
  };

  return (
    <div
      className={cn(
        "flex flex-col gap-1 rounded-lg border border-border bg-card p-4",
        className,
      )}
    >
      <span className="text-2xl font-bold text-foreground">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
      {change ? (
        <span className={cn("text-[11px] font-medium", changeColors[changeVariant])}>
          {change}
        </span>
      ) : null}
    </div>
  );
}
