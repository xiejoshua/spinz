import type { SVGProps } from "react";

/**
 * Full star — closed convex polygon.
 * 24x24 viewBox, geometry symmetric around x=12.
 */
const STAR_PATH =
  "M12 2.5l2.95 6.4 7.05 0.85-5.2 4.85 1.4 7.05L12 18.2 5.8 21.65l1.4-7.05L2 9.75l7.05-0.85z";

/**
 * Literal LEFT-HALF of a star (Letterboxd-style).
 * Traces: top center → down centerline → bottom-left tip → left-bottom inner
 *       → left tip → upper-left inner → close (back to top center).
 * The right side of this glyph is a clean vertical edge at x=12, NOT a clipped full star.
 */
const STAR_LEFT_HALF_PATH =
  "M12 2.5L12 18.2 5.8 21.65l1.4-7.05L2 9.75l7.05-0.85z";

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
      <path d={STAR_PATH} />
    </svg>
  );
}

/**
 * Half star — the literal left half of a star, solid filled.
 * No right-side outline. Letterboxd-exact.
 */
export function StarHalfIcon({
  size = 24,
  ...props
}: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d={STAR_LEFT_HALF_PATH} />
    </svg>
  );
}
