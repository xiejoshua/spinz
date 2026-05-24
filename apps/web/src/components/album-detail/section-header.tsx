type Props = {
  id?: string;
  /** Small-caps mono label e.g. "FRIENDS WHO LOGGED THIS" */
  label: string;
  /** Optional count rendered as a mono pill on the right side of the rule */
  count?: number;
};

/**
 * Editorial section header for album-detail surfaces — small-caps
 * mono label on the left, optional count chip on the right, hairline
 * rule below the row. Mirrors the magazine eyebrow → headline →
 * separator stack used across the rest of the (app) shell.
 */
export function SectionHeader({ id, label, count }: Props) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-4">
        <h2
          id={id}
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          {label}
        </h2>
        {typeof count === "number" && (
          <span
            className="font-mono tabular-nums"
            style={{
              fontSize: "11px",
              letterSpacing: "0.05em",
              color: "var(--muted)",
            }}
          >
            {count}
          </span>
        )}
      </div>
      <div className="h-px" style={{ background: "var(--separator)" }} />
    </div>
  );
}
