import { cn } from "@/lib/cn";
import { Sparkline } from "@/components/ui/Sparkline";

type MetricCardProps = {
  label: string;
  value: number | string;
  change?: string;
  changeVariant?: "success" | "warning" | "muted" | "down";
  up?: boolean;
  sparklinePoints?: number[];
  sparklineColor?: string;
  className?: string;
};

export function MetricCard({
  label,
  value,
  change,
  changeVariant = "success",
  up = true,
  sparklinePoints,
  sparklineColor,
  className,
}: MetricCardProps) {
  const changeColors = {
    success: "text-teal",
    warning: "text-coral",
    muted: "text-text-muted",
    down: "text-brick",
  };

  const resolvedColor =
    sparklineColor ??
    (changeVariant === "down" || up === false ? "#B32107" : "#047857");

  return (
    <div
      className={cn(
        "rounded-2xl border border-line bg-white px-5 py-4 shadow-soft",
        className,
      )}
    >
      <span className="text-[12.5px] font-medium text-text-muted">{label}</span>
      <div className="mt-2 flex items-end justify-between gap-2">
        <div>
          <div className="text-[28px] font-bold leading-none tracking-tight text-ink">
            {value}
          </div>
          {change ? (
            <div className="mt-1.5 flex items-center gap-1">
              <span
                className={cn(
                  "text-[11.5px] font-medium",
                  changeColors[changeVariant],
                )}
              >
                {change}
              </span>
            </div>
          ) : null}
        </div>
        {sparklinePoints && sparklinePoints.length > 1 ? (
          <Sparkline points={sparklinePoints} color={resolvedColor} />
        ) : null}
      </div>
    </div>
  );
}
