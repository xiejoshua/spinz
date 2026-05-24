import type { SVGProps } from "react";

export function StarIcon({
  filled = true,
  size = 24,
  ...props
}: SVGProps<SVGSVGElement> & { filled?: boolean; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d="M12 2.5l2.95 6.4 7.05 0.85-5.2 4.85 1.4 7.05L12 18.2 5.8 21.65l1.4-7.05L2 9.75l7.05-0.85z" />
    </svg>
  );
}

export function StarHalfIcon({
  size = 24,
  ...props
}: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <defs>
        <linearGradient id="star-half-gradient">
          <stop offset="50%" stopColor="currentColor" />
          <stop offset="50%" stopColor="transparent" />
        </linearGradient>
      </defs>
      <path
        d="M12 2.5l2.95 6.4 7.05 0.85-5.2 4.85 1.4 7.05L12 18.2 5.8 21.65l1.4-7.05L2 9.75l7.05-0.85z"
        fill="url(#star-half-gradient)"
      />
    </svg>
  );
}
