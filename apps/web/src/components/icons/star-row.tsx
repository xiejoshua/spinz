import { StarHalfIcon, StarIcon } from "./star";

type StarRowProps = {
  value: number; // 0 .. 5 in half-star increments
  size?: number;
  className?: string;
};

export function StarRow({ value, size = 18, className }: StarRowProps) {
  const full = Math.floor(value);
  const hasHalf = value - full >= 0.5;
  const empty = 5 - full - (hasHalf ? 1 : 0);

  return (
    <span className={className} aria-label={`${value} out of 5 stars`}>
      {Array.from({ length: full }).map((_, i) => (
        <StarIcon key={`f-${i}`} size={size} filled style={{ display: "inline-block" }} />
      ))}
      {hasHalf && (
        <StarHalfIcon size={size} style={{ display: "inline-block" }} />
      )}
      {Array.from({ length: empty }).map((_, i) => (
        <StarIcon key={`e-${i}`} size={size} filled={false} style={{ display: "inline-block", opacity: 0.25 }} />
      ))}
    </span>
  );
}
