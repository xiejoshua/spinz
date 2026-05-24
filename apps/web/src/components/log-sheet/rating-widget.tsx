"use client";

import { StarHalfIcon, StarIcon } from "@/components/icons/star";
import { type KeyboardEvent, type MouseEvent, useState } from "react";

type Props = {
  value: number | null;
  onChange: (value: number | null) => void;
};

const SLOTS = [1, 2, 3, 4, 5] as const;

/**
 * Editorial ½-star rating widget.
 *  - Empty slots:  full star outline in --accent (burgundy)
 *  - Half slot:    literal LEFT half of a star (Letterboxd-exact),
 *                  fill in --accent
 *  - Full slot:    filled star in --accent
 * Two half-width hit zones per slot for ½ vs whole rating.
 */
export function RatingWidget({ value, onChange }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const display = hover ?? value ?? 0;

  function handleClick(slot: number, side: "left" | "right") {
    const next = side === "left" ? slot - 0.5 : slot;
    onChange(next === value ? null : next);
  }

  function handleKey(event: KeyboardEvent<HTMLDivElement>) {
    const current = value ?? 0;
    if (event.key === "ArrowRight" || event.key === "ArrowUp") {
      event.preventDefault();
      onChange(Math.min(5, current + 0.5));
    } else if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
      event.preventDefault();
      const next = Math.max(0, current - 0.5);
      onChange(next === 0 ? null : next);
    } else if (event.key === "Backspace" || event.key === "Delete" || event.key === "0") {
      event.preventDefault();
      onChange(null);
    }
  }

  return (
    <div
      role="slider"
      aria-label="Rating"
      aria-valuenow={value ?? 0}
      aria-valuemin={0}
      aria-valuemax={5}
      aria-valuetext={value == null ? "no rating" : `${value} stars`}
      tabIndex={0}
      onKeyDown={handleKey}
      onMouseLeave={() => setHover(null)}
      className="inline-flex items-center gap-3 rounded-md px-1 py-1 focus-visible:outline-none focus-visible:ring-2"
      style={{
        // biome-ignore lint/suspicious/noExplicitAny: CSS custom property key needs cast to satisfy React.CSSProperties index signature
        ["--tw-ring-color" as any]: "var(--focus)",
      }}
    >
      <div className="inline-flex items-center gap-1" style={{ color: "var(--accent)" }}>
        {SLOTS.map((slot) => (
          <StarSlot
            key={slot}
            slot={slot}
            display={display}
            onPointerEnterLeft={() => setHover(slot - 0.5)}
            onPointerEnterRight={() => setHover(slot)}
            onClickLeft={() => handleClick(slot, "left")}
            onClickRight={() => handleClick(slot, "right")}
          />
        ))}
      </div>
      <span
        aria-hidden="true"
        className="font-mono tabular-nums"
        style={{
          fontSize: "13px",
          color: "var(--muted)",
          letterSpacing: "0.04em",
        }}
      >
        {value == null ? "—" : value.toFixed(1)}
      </span>
    </div>
  );
}

type SlotProps = {
  slot: number;
  display: number;
  onPointerEnterLeft: () => void;
  onPointerEnterRight: () => void;
  onClickLeft: () => void;
  onClickRight: () => void;
};

function StarSlot({
  slot,
  display,
  onPointerEnterLeft,
  onPointerEnterRight,
  onClickLeft,
  onClickRight,
}: SlotProps) {
  const isFull = display >= slot;
  const isHalf = !isFull && display >= slot - 0.5;
  const halfHandler = (handler: () => void) => (e: MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    handler();
  };
  return (
    <div className="relative" style={{ width: 32, height: 32, lineHeight: 0 }}>
      {isFull ? (
        <StarIcon size={32} filled />
      ) : isHalf ? (
        <StarHalfIcon size={32} />
      ) : (
        <StarIcon size={32} filled={false} />
      )}
      <button
        type="button"
        aria-label={`Set rating to ${slot - 0.5} stars`}
        onMouseEnter={onPointerEnterLeft}
        onClick={halfHandler(onClickLeft)}
        className="absolute inset-y-0 left-0 w-1/2 cursor-pointer bg-transparent"
      />
      <button
        type="button"
        aria-label={`Set rating to ${slot} stars`}
        onMouseEnter={onPointerEnterRight}
        onClick={halfHandler(onClickRight)}
        className="absolute inset-y-0 right-0 w-1/2 cursor-pointer bg-transparent"
      />
    </div>
  );
}
