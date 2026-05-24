import { AuxIcon } from "@/components/icons/aux";
import { StarRow } from "@/components/icons/star-row";
import type { AlbumAggregate, AlbumPayload } from "@/lib/album-types";
import { EditionSelector } from "./edition-selector";

type Props = {
  album: AlbumPayload;
  aggregate: AlbumAggregate;
  editions: AlbumPayload[];
};

function formatRuntime(ms: number | null): string | null {
  if (ms == null || ms === 0) return null;
  const totalMinutes = Math.round(ms / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function formatCompact(n: number): string {
  if (n >= 10_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, "")}k`;
  if (n >= 1_000) return n.toLocaleString();
  return String(n);
}

export function AlbumHero({ album, aggregate, editions }: Props) {
  const runtime = formatRuntime(album.duration_ms);
  const trackCount = album.tracklist.length;
  const meta = [
    album.release_year ? String(album.release_year) : null,
    album.label,
    trackCount > 0 ? `${trackCount} tracks` : null,
    runtime,
  ].filter(Boolean);
  const hasEditions = editions.length > 1;
  return (
    <header className="space-y-8">
      {/* Magazine treatment — cover-art and title share the same baseline.
          On mobile the cover stacks above; on sm+ they sit side by side. */}
      <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:gap-8">
        <CoverArt album={album} />
        <div className="min-w-0 flex-1 space-y-4">
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "11px",
              letterSpacing: "0.18em",
              color: "var(--muted)",
            }}
          >
            Album
          </div>
          <h1
            className="font-serif font-semibold leading-[1.02] tracking-[-0.02em]"
            style={{
              fontSize: "clamp(36px, 6vw, 64px)",
              color: "var(--foreground)",
              fontFamily: "var(--font-serif)",
            }}
          >
            {album.title}
          </h1>
          <p
            className="font-sans"
            style={{
              fontSize: "20px",
              color: "var(--foreground)",
              fontWeight: 500,
            }}
          >
            {album.artist_credit}
          </p>
          {meta.length > 0 && (
            <p
              className="font-mono"
              style={{
                fontSize: "12px",
                letterSpacing: "0.04em",
                color: "var(--muted)",
              }}
            >
              {meta.join(" · ")}
            </p>
          )}
        </div>
      </div>

      {/* Genre chips */}
      {album.genres.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {album.genres.slice(0, 5).map((g) => (
            <span
              key={g}
              className="font-mono uppercase"
              style={{
                fontSize: "10px",
                letterSpacing: "0.18em",
                padding: "5px 10px",
                borderRadius: "999px",
                border: "1px solid var(--border)",
                color: "var(--muted)",
                background: "transparent",
              }}
            >
              {g}
            </span>
          ))}
        </div>
      )}

      {/* Stat strip — Newsreader tabular numbers; only renders if there's
          activity, otherwise we show a quiet "be the first" line below. */}
      {aggregate.rating_count > 0 ? (
        <dl
          className="grid grid-cols-2 gap-y-4 sm:grid-cols-4"
          style={{
            borderTop: "1px solid var(--separator)",
            borderBottom: "1px solid var(--separator)",
            paddingTop: "18px",
            paddingBottom: "18px",
          }}
        >
          <Stat
            label="Avg rating"
            value={aggregate.avg_rating.toFixed(1)}
            decoration={
              <StarRow
                value={aggregate.avg_rating}
                size={12}
                className="mt-1 block"
              />
            }
          />
          <Stat label="Logs" value={formatCompact(aggregate.rating_count)} />
          <Stat
            label="Aux'd"
            value={formatCompact(aggregate.aux_count)}
            valueColor="var(--gold)"
            decoration={
              <span
                aria-hidden
                className="inline-flex items-center"
                style={{ color: "var(--gold)" }}
              >
                <AuxIcon filled size={12} />
              </span>
            }
          />
          <Stat label="Reviews" value={formatCompact(aggregate.review_count)} />
        </dl>
      ) : (
        <p
          className="font-sans text-[14px]"
          style={{
            color: "var(--muted)",
            borderTop: "1px solid var(--separator)",
            paddingTop: "16px",
          }}
        >
          No logs yet — be the first to rate this album.
        </p>
      )}

      {/* Edition selector (only when multiple editions exist) */}
      {hasEditions && (
        <div className="flex items-center gap-3">
          <span
            className="font-mono uppercase"
            style={{
              fontSize: "10px",
              letterSpacing: "0.18em",
              color: "var(--muted)",
            }}
          >
            Edition
          </span>
          <EditionSelector editions={editions} currentId={album.id} />
        </div>
      )}
    </header>
  );
}

function Stat({
  label,
  value,
  valueColor,
  decoration,
}: {
  label: string;
  value: string;
  valueColor?: string;
  decoration?: React.ReactNode;
}) {
  return (
    <div>
      <dt
        className="font-mono uppercase"
        style={{
          fontSize: "10px",
          letterSpacing: "0.15em",
          color: "var(--muted)",
        }}
      >
        {label}
      </dt>
      <dd
        className="mt-1 flex items-baseline gap-2 font-serif tabular-nums"
        style={{
          fontSize: "26px",
          fontWeight: 600,
          color: valueColor ?? "var(--foreground)",
          fontFamily: "var(--font-serif)",
        }}
      >
        {value}
        {decoration && <span style={{ fontSize: "12px" }}>{decoration}</span>}
      </dd>
    </div>
  );
}

function CoverArt({ album }: { album: AlbumPayload }) {
  const size = 280;
  const src = album.mbid
    ? `/api/cover/500/${album.mbid}${album.cover_art_url ? `?fallback=${encodeURIComponent(album.cover_art_url)}` : ""}`
    : album.cover_art_url;
  const sharedClasses =
    "size-60 shrink-0 self-start rounded-md object-cover shadow-lg sm:size-[280px]";
  const sharedStyle = {
    background:
      "linear-gradient(135deg, var(--surface-secondary), var(--surface-tertiary))",
  };
  if (!src) {
    return (
      <div
        aria-hidden="true"
        className={sharedClasses}
        style={sharedStyle}
      />
    );
  }
  return (
    <img
      src={src}
      alt={`Cover of ${album.title}`}
      width={size}
      height={size}
      className={sharedClasses}
      style={sharedStyle}
    />
  );
}
