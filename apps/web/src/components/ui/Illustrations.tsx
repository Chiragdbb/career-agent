export function TrailMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <circle cx="16" cy="16" r="16" fill="#D63B20" />
      <path
        d="M10 18.5L16 9L22 18.5H18.5L16 14.5L13.5 18.5H10Z"
        fill="white"
      />
      <circle cx="16" cy="21.5" r="1.75" fill="white" />
    </svg>
  );
}

export function OnboardingIllustration() {
  return (
    <svg width="120" height="90" viewBox="0 0 120 90" fill="none" aria-hidden>
      <circle cx="90" cy="30" r="28" fill="#FFDAD3" opacity="0.7" />
      <circle cx="40" cy="50" r="22" fill="#E2DFFF" opacity="0.8" />
      <path
        d="M20 70 C 40 60, 55 75, 75 55 S 95 35, 110 40"
        stroke="#D63B20"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="110" cy="40" r="4" fill="#D63B20" />
    </svg>
  );
}

export function EmptyDoodle() {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none" aria-hidden>
      <circle cx="36" cy="36" r="30" fill="#FEF7FF" stroke="#EBE4F0" strokeWidth="1.5" />
      <path
        d="M24 40 Q36 24 48 40"
        stroke="#D63B20"
        strokeWidth="2.2"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="28" cy="46" r="2" fill="#0C006B" />
      <circle cx="44" cy="46" r="2" fill="#0C006B" />
    </svg>
  );
}

export function MomentumOrb({ className }: { className?: string }) {
  return (
    <div
      className={className}
      aria-hidden
      style={{
        background:
          "radial-gradient(circle at 40% 40%, #ffdad3 0%, rgba(214,59,32,0.35) 45%, rgba(194,193,255,0.5) 100%)",
        borderRadius: "9999px",
        filter: "blur(2px)",
      }}
    />
  );
}
