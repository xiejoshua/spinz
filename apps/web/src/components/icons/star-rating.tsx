"use client";

import { useState } from "react";
import { StarHalfIcon, StarIcon } from "./star";

type StarRatingProps = {
  value: number;
  onChange: (next: number) => void;
  max?: number;
  size?: number;
  className?: string;
};

/**
 * Letterboxd-style interactive rating.
 *  - Full positions: filled star (currentColor)
 *  - Half position:  literal left-half star geometry (currentColor)
 *  - Empty positions: empty star outline (color = var(--accent))
 *
 * Each star has two half-width click zones so users can land on .5 or .0.
 * Click value V toggles back to 0 if you click the exact same V again.
 */
export function StarRating({
  value,
  onChange,
  max = 5,
  size = 28,
  className,
}: StarRatingProps) {
  const [hover, setHover] = useState<number | null>(null);
  const display = hover ?? value;

  return (
    <div
      className={className}
      role="radiogroup"
      aria-label="Rate this album"
      onMouseLeave={() => setHover(null)}
      style={{ display: "inline-flex", alignItems: "center", gap: 2 }}
    >
      {Array.from({ length: max }).map((_, i) => {
        const position = i + 1;
        const isFull = display >= position;
        const isHalf = !isFull && display >= position - 0.5;
        const valueLeft = position - 0.5;
        const valueRight = position;
        return (
          <div
            key={i}
            style={{
              position: "relative",
              width: size,
              height: size,
              lineHeight: 0,
              color: "var(--accent)",
            }}
          >
            {/* visual layer */}
            {isFull ? (
              <StarIcon size={size} filled />
            ) : isHalf ? (
              <StarHalfIcon size={size} />
            ) : (
              <StarIcon size={size} filled={false} />
            )}

            {/* interaction overlay — two half-width click targets */}
            <button
              type="button"
              aria-label={`${valueLeft} stars`}
              onMouseEnter={() => setHover(valueLeft)}
              onClick={() =>
                onChange(value === valueLeft ? 0 : valueLeft)
              }
              style={{
                position: "absolute",
                inset: 0,
                width: "50%",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: 0,
              }}
            />
            <button
              type="button"
              aria-label={`${valueRight} stars`}
              onMouseEnter={() => setHover(valueRight)}
              onClick={() =>
                onChange(value === valueRight ? 0 : valueRight)
              }
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                right: 0,
                width: "50%",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: 0,
              }}
            />
          </div>
        );
      })}
    </div>
  );
}
