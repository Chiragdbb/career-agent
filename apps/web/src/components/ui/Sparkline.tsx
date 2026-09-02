type SparklineProps = {
  points: number[];
  color?: string;
  className?: string;
};

export function Sparkline({
  points,
  color = "#2E6B59",
  className,
}: SparklineProps) {
  const w = 84;
  const h = 28;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const norm = points
    .map((p, i) => {
      const x = (i / (points.length - 1 || 1)) * w;
      const y = h - ((p - min) / (max - min || 1)) * h;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      className={className}
      aria-hidden
    >
      <polyline
        points={norm}
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
