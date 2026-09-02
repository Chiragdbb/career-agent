type ScoreRingProps = {
  value: number;
  size?: number;
  className?: string;
};

export function ScoreRing({ value, size = 64, className }: ScoreRingProps) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;

  return (
    <div
      className={className}
      style={{ position: "relative", width: size, height: size }}
    >
      <svg width={size} height={size} aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="#E7E4D6"
          strokeWidth="5"
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="#B9822E"
          strokeWidth="5"
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{
            transition: "stroke-dashoffset 900ms cubic-bezier(0.22, 1, 0.36, 1)",
          }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-serif text-base font-semibold text-ink">{value}</span>
      </div>
    </div>
  );
}
