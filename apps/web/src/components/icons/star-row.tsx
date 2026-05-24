import { StarHalfIcon, StarIcon } from "./star";

type StarRowProps = {
  value: number; // 0..5 in half-star increments
  size?: number;
  max?: number;
  className?: string;
};

export function StarRow({
  value,
  size = 18,
  max = 5,
  className,
}: StarRowProps) {
  return (
    <span className={className} aria-label={`${value} out of ${max} stars`}>
      {Array.from({ length: max }).map((_, i) => {
        const position = i + 1;
        const isFull = value >= position;
        const isHalf = !isFull && value >= position - 0.5;
        if (isFull) {
          return (
            <StarIcon
              key={i}
              size={size}
              filled
              style={{ display: "inline-block" }}
            />
          );
        }
        if (isHalf) {
          return (
            <StarHalfIcon
              key={i}
              size={size}
              style={{ display: "inline-block" }}
            />
          );
        }
        return (
          <StarIcon
            key={i}
            size={size}
            filled={false}
            style={{
              display: "inline-block",
              color: "var(--accent)",
            }}
          />
        );
      })}
    </span>
  );
}
