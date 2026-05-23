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
    <section aria-labelledby="tracklist-heading" className="space-y-2">
      <h2 id="tracklist-heading" className="text-lg font-semibold">
        Tracklist
      </h2>
      <ol className="divide-y rounded-md border">
        {tracks.map((track) => (
          <li
            key={`${track.position}-${track.title}`}
            className="flex items-center gap-3 px-3 py-2 text-sm"
          >
            <span className="w-6 shrink-0 text-right text-muted-foreground">{track.position}</span>
            <span className="min-w-0 flex-1 truncate">{track.title}</span>
            <span className="shrink-0 text-muted-foreground">
              {formatDuration(track.duration_ms)}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
