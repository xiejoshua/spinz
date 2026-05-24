"use client";

import { cn } from "@/lib/utils";
import { Star, StarHalf } from "lucide-react";
import { type KeyboardEvent, type MouseEvent, useState } from "react";

type Props = {
  value: number | null;
  onChange: (value: number | null) => void;
};

const SLOTS = [1, 2, 3, 4, 5] as const;

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
      className="flex items-center gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md px-1 py-1"
    >
      <div className="flex">
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
      <span aria-hidden="true" className="text-sm tabular-nums text-muted-foreground">
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
  const filledFull = display >= slot;
  const filledHalf = !filledFull && display >= slot - 0.5;
  const halfHandler = (handler: () => void) => (e: MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    handler();
  };
  return (
    <div className="relative">
      {filledHalf ? (
        <StarHalf
          className="size-8 fill-foreground stroke-foreground transition-colors duration-200 ease-out"
          aria-hidden="true"
        />
      ) : filledFull ? (
        <Star
          className="size-8 fill-foreground stroke-foreground transition-colors duration-200 ease-out"
          aria-hidden="true"
        />
      ) : (
        <Star
          className="size-8 fill-transparent stroke-muted-foreground transition-colors duration-200 ease-out"
          aria-hidden="true"
        />
      )}
      <button
        type="button"
        aria-label={`Set rating to ${slot - 0.5} stars`}
        onMouseEnter={onPointerEnterLeft}
        onClick={halfHandler(onClickLeft)}
        className="absolute inset-y-0 left-0 w-1/2"
      />
      <button
        type="button"
        aria-label={`Set rating to ${slot} stars`}
        onMouseEnter={onPointerEnterRight}
        onClick={halfHandler(onClickRight)}
        className="absolute inset-y-0 right-0 w-1/2"
      />
    </div>
  );
}
