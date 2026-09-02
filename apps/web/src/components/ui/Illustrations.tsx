export function TrailMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <circle cx="16" cy="16" r="15" stroke="#E6C98A" strokeWidth="1.2" />
      <path
        d="M7 21 C 11 15, 13 22, 17 14 S 23 10, 25 12"
        stroke="#B9822E"
        strokeWidth="1.6"
        fill="none"
        strokeLinecap="round"
      />
      <circle cx="25" cy="12" r="2" fill="#B9822E" />
    </svg>
  );
}

export function OnboardingIllustration() {
  return (
    <svg width="120" height="90" viewBox="0 0 120 90" fill="none" aria-hidden>
      <path
        d="M6 74 C 30 74, 26 40, 48 40 S 62 66, 84 56 S 96 22, 112 18"
        stroke="#E6C98A"
        strokeWidth="2"
        strokeDasharray="1 7"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="6" cy="74" r="4" fill="#2E6B59" />
      <circle cx="48" cy="40" r="3.5" fill="#E6C98A" />
      <circle cx="84" cy="56" r="3.5" fill="#E6C98A" />
      <g transform="translate(103,6)">
        <path d="M2 30 V2" stroke="#16231F" strokeWidth="2" strokeLinecap="round" />
        <path d="M2 2 L18 7 L2 12 Z" fill="#B9822E" />
      </g>
    </svg>
  );
}

export function EmptyDoodle() {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none" aria-hidden>
      <circle cx="36" cy="36" r="30" fill="#F1EFE5" stroke="#DCD9CA" strokeWidth="1.5" />
      <path
        d="M24 40 Q36 24 48 40"
        stroke="#E6C98A"
        strokeWidth="2.2"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="28" cy="46" r="2" fill="#B9822E" />
      <circle cx="44" cy="46" r="2" fill="#B9822E" />
    </svg>
  );
}
