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
    warning: "text-gold",
    muted: "text-text-muted",
    down: "text-brick",
  };

  const resolvedColor =
    sparklineColor ??
    (changeVariant === "down" || up === false ? "#AA4630" : "#2E6B59");

  return (
    <div
      className={cn(
        "rounded-xl border border-line bg-paper-raised px-[18px] py-4",
        className,
      )}
    >
      <span className="text-[12.5px] text-text-muted">{label}</span>
      <div className="mt-2 flex items-end justify-between gap-2">
        <div>
          <div className="font-serif text-[28px] font-semibold leading-none text-ink">
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
