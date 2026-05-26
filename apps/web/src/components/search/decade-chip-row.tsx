"use client";

type Decade = "2020s" | "2010s" | "2000s" | "1990s" | "1980s" | "earlier";

type Props = {
  selected: Set<Decade>;
  onChange: (next: Set<Decade>) => void;
};

const DECADES: ReadonlyArray<{ value: Decade; label: string }> = [
  { value: "2020s", label: "2020s" },
  { value: "2010s", label: "2010s" },
  { value: "2000s", label: "2000s" },
  { value: "1990s", label: "1990s" },
  { value: "1980s", label: "1980s" },
  { value: "earlier", label: "Earlier" },
];

/**
 * Horizontal chip row for multi-selecting decade filters on the
 * advanced search surface. Mobile-first (no left rail). "Earlier"
 * maps to every decade-bucket before 1980 on the backend.
 */
export function DecadeChipRow({ selected, onChange }: Props) {
  const toggle = (value: Decade) => {
    const next = new Set(selected);
    if (next.has(value)) {
      next.delete(value);
    } else {
      next.add(value);
    }
    onChange(next);
  };
  return (
    // biome-ignore lint/a11y/useSemanticElements: chip row is purposefully styled, not a fieldset
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by decade">
      {DECADES.map((d) => {
        const active = selected.has(d.value);
        return (
          <button
            key={d.value}
            type="button"
            aria-pressed={active}
            onClick={() => toggle(d.value)}
            className="decade-chip px-3 py-1.5 font-sans text-[12px] font-medium leading-none transition-colors"
            style={{
              borderRadius: "9999px",
              background: active ? "var(--accent)" : "transparent",
              color: active ? "var(--accent-foreground)" : "var(--foreground)",
              border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
              cursor: "pointer",
            }}
          >
            {d.label}
          </button>
        );
      })}
      <style>{`
        .decade-chip:focus-visible {
          outline: 2px solid var(--focus);
          outline-offset: 2px;
        }
      `}</style>
    </div>
  );
}

export type { Decade };
export const DECADE_VALUES: ReadonlyArray<Decade> = DECADES.map((d) => d.value);
