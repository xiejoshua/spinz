"use client";

import { cn } from "@/lib/utils";

type Props = {
  value: boolean;
  onChange: (value: boolean) => void;
};

export function AuxToggle({ value, onChange }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      aria-label="Aux'd — mark as a personal standout"
      onClick={() => onChange(!value)}
      className={cn(
        "flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        value
          ? "border-foreground bg-foreground/5 text-foreground"
          : "border-border text-muted-foreground hover:bg-muted"
      )}
    >
      <span aria-hidden="true" className={cn("text-lg", value ? "" : "opacity-40 grayscale")}>
        🏅
      </span>
      <span>{value ? "Aux'd" : "Aux"}</span>
    </button>
  );
}
