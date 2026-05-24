import type { SVGProps } from "react";

export function LikeIcon({
  filled = false,
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
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d="M7 11v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3z" />
      <path d="M7 11l4.5-7a2.5 2.5 0 0 1 4.5 2v3h4.5a2 2 0 0 1 2 2.3l-1.4 6.4a2 2 0 0 1-2 1.6H7" />
    </svg>
  );
}
