import { SectionHeader } from "@/components/album-detail/section-header";
import { AuxIcon } from "@/components/icons/aux";
import { StarRow } from "@/components/icons/star-row";
import type { DiaryRow } from "@/lib/album-types";

type Props = {
  history: DiaryRow[];
};

export function MyHistory({ history }: Props) {
  if (history.length === 0) {
    return null;
  }
  return (
    <section aria-labelledby="my-history-heading" className="space-y-4">
      <SectionHeader
        id="my-history-heading"
        label="Your history"
        count={history.length}
      />
      <ul>
        {history.map((entry, i) => (
          <li
            key={entry.id}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 py-3"
            style={{
              borderBottom:
                i < history.length - 1
                  ? "1px solid var(--separator)"
                  : "none",
            }}
          >
            <span
              className="font-mono"
              style={{
                fontSize: "12px",
                color: "var(--muted)",
                minWidth: "100px",
              }}
            >
              {new Date(entry.logged_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
              })}
            </span>
            {entry.rating != null && (
              <span
                className="inline-flex items-center gap-1.5"
                style={{ color: "var(--accent)" }}
              >
                <StarRow value={entry.rating} size={14} />
                <span
                  className="font-mono tabular-nums"
                  style={{ fontSize: "12px", color: "var(--muted)" }}
                >
                  {entry.rating.toFixed(1)}
                </span>
              </span>
            )}
            {entry.auxed && (
              <span
                className="inline-flex items-center gap-1 font-mono uppercase"
                style={{
                  fontSize: "10px",
                  letterSpacing: "0.15em",
                  color: "var(--gold)",
                }}
              >
                <AuxIcon filled size={12} /> Aux'd
              </span>
            )}
            {entry.visibility !== "public" && (
              <span
                className="font-mono uppercase"
                style={{
                  fontSize: "10px",
                  letterSpacing: "0.15em",
                  color: "var(--muted)",
                }}
              >
                {entry.visibility}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
