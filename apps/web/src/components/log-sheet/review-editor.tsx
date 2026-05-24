"use client";

import { ChevronDown, Pencil } from "lucide-react";
import { useState } from "react";

type Props = {
  value: string;
  onChange: (value: string) => void;
};

const MAX_LENGTH = 10_000;

export function ReviewEditor({ value, onChange }: Props) {
  const [expanded, setExpanded] = useState(value.length > 0);

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="inline-flex cursor-pointer items-center gap-2 font-sans text-[14px] hover:underline"
        style={{ color: "var(--muted)" }}
      >
        <Pencil className="size-4" aria-hidden="true" />
        Add a review
      </button>
    );
  }

  return (
    <div className="space-y-1.5">
      <label htmlFor="log-review" className="sr-only">
        Review
      </label>
      <textarea
        id="log-review"
        rows={5}
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, MAX_LENGTH))}
        placeholder="What did you think?"
        className="block w-full resize-y rounded-md px-4 py-3 font-sans text-[15px] leading-[1.55] focus:outline-none focus:ring-2"
        style={{
          background: "var(--field-background)",
          color: "var(--field-foreground)",
          border: "1px solid var(--field-border)",
          // biome-ignore lint/suspicious/noExplicitAny: CSS custom property key needs cast to satisfy React.CSSProperties index signature
          ["--tw-ring-color" as any]: "var(--focus)",
        }}
      />
      <div
        className="flex items-center justify-between font-mono"
        style={{ fontSize: "11px", color: "var(--muted)" }}
      >
        <button
          type="button"
          onClick={() => {
            onChange("");
            setExpanded(false);
          }}
          className="inline-flex cursor-pointer items-center gap-1 uppercase tracking-[0.12em] hover:underline"
        >
          <ChevronDown className="size-3" aria-hidden="true" />
          Collapse
        </button>
        <span className="tabular-nums">
          {value.length} / {MAX_LENGTH.toLocaleString()}
        </span>
      </div>
    </div>
  );
}
