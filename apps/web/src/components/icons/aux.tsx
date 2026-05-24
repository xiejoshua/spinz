import type { SVGProps } from "react";

export function AuxIcon({
  filled = false,
  size = 24,
  ...props
}: SVGProps<SVGSVGElement> & { filled?: boolean; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {/* Laurel half-wreath, left side */}
      <path
        d="M5 6c-1 3-1 6 0.5 9c1.4 2.8 3.7 4.5 6.5 5"
        fill={filled ? "var(--gold-soft, transparent)" : "none"}
      />
      <path d="M5.2 7.5c1 0.5 1.6 1.3 1.8 2.4" />
      <path d="M5 11c1.1 0.4 1.8 1.2 2.1 2.4" />
      <path d="M5.6 14.4c1.2 0.3 2 1.1 2.4 2.3" />
      {/* Laurel half-wreath, right side */}
      <path
        d="M19 6c1 3 1 6-0.5 9c-1.4 2.8-3.7 4.5-6.5 5"
        fill={filled ? "var(--gold-soft, transparent)" : "none"}
      />
      <path d="M18.8 7.5c-1 0.5-1.6 1.3-1.8 2.4" />
      <path d="M19 11c-1.1 0.4-1.8 1.2-2.1 2.4" />
      <path d="M18.4 14.4c-1.2 0.3-2 1.1-2.4 2.3" />
      {/* Center medallion */}
      <circle
        cx="12"
        cy="11"
        r="2.25"
        fill={filled ? "currentColor" : "none"}
      />
    </svg>
  );
}
