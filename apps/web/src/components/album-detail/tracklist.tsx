import { SectionHeader } from "@/components/album-detail/section-header";
import type { Track } from "@/lib/album-types";

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function Tracklist({ tracks }: { tracks: Track[] }) {
  return (
    <section aria-labelledby="tracklist-heading" className="space-y-4">
      <SectionHeader
        id="tracklist-heading"
        label="Tracklist"
        count={tracks.length}
      />
      <ol>
        {tracks.map((track, i) => (
          <li
            key={`${track.position}-${track.title}`}
            className="flex items-center gap-4 py-2.5"
            style={{
              borderBottom:
                i < tracks.length - 1
                  ? "1px solid var(--separator)"
                  : "none",
            }}
          >
            <span
              className="w-7 shrink-0 text-right font-mono tabular-nums"
              style={{
                fontSize: "12px",
                color: "var(--muted)",
                letterSpacing: "0.02em",
              }}
            >
              {String(track.position).padStart(2, "0")}
            </span>
            <span
              className="min-w-0 flex-1 truncate font-serif"
              style={{
                fontSize: "15px",
                color: "var(--foreground)",
                fontFamily: "var(--font-serif)",
              }}
            >
              {track.title}
            </span>
            <span
              className="shrink-0 font-mono tabular-nums"
              style={{
                fontSize: "12px",
                color: "var(--muted)",
              }}
            >
              {formatDuration(track.duration_ms)}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
