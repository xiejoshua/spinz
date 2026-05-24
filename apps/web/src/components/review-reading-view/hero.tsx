import { AuxIcon } from "@/components/icons/aux";
import { StarRow } from "@/components/icons/star-row";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { AlbumPayload, DiaryRow } from "@/lib/album-types";
import type { Review, ReviewUserCard } from "@/lib/review-types";
import Link from "next/link";

type Props = {
  review: Review;
  user: ReviewUserCard | undefined;
  album: AlbumPayload;
  viewerEntry: DiaryRow | null;
};

export function ReadingHero({ review, user, album, viewerEntry }: Props) {
  const coverUrl = album.mbid
    ? `/api/cover/500/${album.mbid}${album.cover_art_url ? `?fallback=${encodeURIComponent(album.cover_art_url)}` : ""}`
    : album.cover_art_url;
  const handle = user?.handle ?? `user-${review.user_id.slice(0, 8)}`;
  const displayName = user?.display_name ?? handle;
  return (
    <header className="space-y-6">
      {/* Section eyebrow — small caps editorial register */}
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "11px",
          letterSpacing: "0.18em",
          color: "var(--muted)",
        }}
      >
        Review
      </div>

      {/* Headline — Newsreader 40-48px, the album title is the punctum */}
      <Link
        href={`/album/${encodeURIComponent(album.id)}`}
        className="block hover:opacity-90"
      >
        <h1
          className="font-serif font-semibold leading-[1.05] tracking-[-0.015em]"
          style={{
            fontSize: "clamp(32px, 5vw, 48px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          {album.title}
        </h1>
      </Link>

      {/* Sub-subhead — artist + year */}
      <p
        className="font-sans text-[17px] leading-tight"
        style={{ color: "var(--muted)" }}
      >
        {album.artist_credit}
        {album.release_year ? ` · ${album.release_year}` : ""}
      </p>

      {/* Author + rating + edited row */}
      <div
        className="flex flex-wrap items-center gap-3 pt-2"
        style={{ borderTop: "1px solid var(--separator)" }}
      >
        <Avatar className="size-9">
          <AvatarFallback>{handle.slice(0, 2).toUpperCase()}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1 leading-tight">
          <div className="flex items-baseline gap-2">
            <span
              className="font-sans text-[14px] font-semibold"
              style={{ color: "var(--foreground)" }}
            >
              {displayName}
            </span>
            <span
              className="font-mono text-[12px]"
              style={{ color: "var(--muted)" }}
            >
              @{handle}
            </span>
          </div>
          {viewerEntry?.rating != null && (
            <div
              className="mt-1 inline-flex items-center gap-2"
              style={{ color: "var(--accent)" }}
            >
              <StarRow value={viewerEntry.rating} size={14} />
              {viewerEntry.auxed && (
                <span
                  aria-hidden="true"
                  className="inline-flex items-center"
                  style={{ color: "var(--gold)" }}
                >
                  <AuxIcon filled size={14} />
                </span>
              )}
            </div>
          )}
        </div>
        {coverUrl && (
          <Link
            href={`/album/${encodeURIComponent(album.id)}`}
            aria-label={`Open ${album.title}`}
            className="shrink-0"
          >
            <img
              src={coverUrl}
              alt=""
              width={56}
              height={56}
              className="size-14 rounded object-cover"
              style={{ background: "var(--surface-secondary)" }}
            />
          </Link>
        )}
        {review.edited_at && (
          <span
            className="font-mono uppercase"
            style={{
              fontSize: "10px",
              letterSpacing: "0.18em",
              color: "var(--muted)",
            }}
          >
            · edited
          </span>
        )}
      </div>
    </header>
  );
}
