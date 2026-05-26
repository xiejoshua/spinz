import type { DiscoverAlbumSummary, FromFollowsAnnotation } from "@/lib/social-types";
import Link from "next/link";

type Props = {
  album: DiscoverAlbumSummary;
  annotation?: FromFollowsAnnotation;
  onClick?: () => void;
  /**
   * Called once the cover art fails to load (CAA 404 + no usable
   * fallback, or the fallback host itself 404s). Consumers track
   * failures in a Set and filter the album out of subsequent renders
   * — the Discover surfaces are supposed to hide coverless rows, and
   * the backend ``require_cover`` filter only catches metadata-level
   * "definitely no art" cases. Runtime detection covers the rest.
   */
  onCoverFailed?: (albumId: string) => void;
};

/**
 * Editorial album card used across Discover sections. Cover art on
 * top, Newsreader title + sans artist below; optional annotation
 * byline ("@lily rated · 4/5") for the From-Your-Follows surface.
 *
 * Hover lifts the title to the accent colour (matching the
 * search-result-row pattern), and the whole card is a single Link so
 * keyboard tab order stays clean.
 */
export function AlbumCard({ album, annotation, onClick, onCoverFailed }: Props) {
  const year = album.release_year ? `${album.release_year}` : null;
  return (
    <Link
      href={`/album/${album.id}`}
      onClick={onClick}
      className="discover-album-card flex flex-col gap-2"
    >
      <CoverArt album={album} onError={onCoverFailed ? () => onCoverFailed(album.id) : undefined} />
      <div className="min-w-0">
        <p
          className="discover-album-card__title truncate font-serif font-semibold leading-[1.2] tracking-[-0.005em]"
          style={{
            fontSize: "14px",
            fontFamily: "var(--font-serif)",
            color: "var(--foreground)",
          }}
        >
          {album.title}
        </p>
        <p
          className="truncate font-sans text-[12px] leading-[1.4]"
          style={{ color: "var(--muted)" }}
        >
          {album.artist_name}
          {year ? ` · ${year}` : ""}
        </p>
        {annotation && <Annotation annotation={annotation} />}
      </div>
      <style>{`
        .discover-album-card { cursor: pointer; }
        .discover-album-card:hover .discover-album-card__title {
          color: var(--accent);
        }
        .discover-album-card:focus-visible {
          outline: 2px solid var(--focus);
          outline-offset: 2px;
          border-radius: 2px;
        }
      `}</style>
    </Link>
  );
}

function CoverArt({
  album,
  onError,
}: {
  album: DiscoverAlbumSummary;
  onError?: () => void;
}) {
  const baseStyle = {
    background: "var(--surface-secondary)",
    aspectRatio: "1 / 1",
  } as const;
  if (album.mbid) {
    const fallback = album.cover_art_url
      ? `?fallback=${encodeURIComponent(album.cover_art_url)}`
      : "";
    return (
      <img
        src={`/api/cover/500/${album.mbid}${fallback}`}
        alt=""
        loading="lazy"
        onError={onError}
        className="w-full rounded object-cover"
        style={baseStyle}
      />
    );
  }
  if (album.cover_art_url) {
    return (
      <img
        src={album.cover_art_url}
        alt=""
        loading="lazy"
        onError={onError}
        className="w-full rounded object-cover"
        style={baseStyle}
      />
    );
  }
  return (
    <div
      aria-hidden="true"
      className="w-full rounded"
      style={{
        ...baseStyle,
        background: "linear-gradient(135deg, var(--surface-secondary), var(--surface-tertiary))",
      }}
    />
  );
}

function Annotation({ annotation }: { annotation: FromFollowsAnnotation }) {
  const ratingText =
    annotation.verb === "rated" && annotation.rating !== null
      ? ` · ${annotation.rating.toFixed(annotation.rating % 1 === 0 ? 0 : 1)}/5`
      : "";
  return (
    <p
      className="mt-1 truncate font-sans text-[11px] leading-[1.4]"
      style={{ color: "var(--accent)" }}
    >
      @{annotation.actor_handle} {annotation.verb}
      {ratingText}
    </p>
  );
}
