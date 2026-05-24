"use client";

import { AuxIcon } from "@/components/icons/aux";
import { StarRow } from "@/components/icons/star-row";
import { Badge } from "@/components/ui/badge";
import type { DiaryAlbumCard, DiaryEntry, DiaryReviewCard } from "@/lib/diary-types";
import { renderReviewBody } from "@/lib/review-body";
import Link from "next/link";

type Props = {
  entry: DiaryEntry;
  album: DiaryAlbumCard | undefined;
  review?: DiaryReviewCard;
  showOwnerControls?: boolean;
  onEdit?: (entry: DiaryEntry) => void;
  onDelete?: (entry: DiaryEntry) => void;
};

const PREVIEW_CHARS = 220;

/**
 * Editorial diary entry card — hairline separator between siblings
 * (rendered here on each card), cover thumb + title + artist + metadata
 * row + optional review excerpt rendered as Newsreader serif body
 * matching the dedicated review reading view. Owner controls (Edit /
 * Delete) sit at the bottom in muted mono small-caps.
 */
export function DiaryEntryCard({
  entry,
  album,
  review,
  showOwnerControls,
  onEdit,
  onDelete,
}: Props) {
  const coverUrl = album?.mbid
    ? `/api/cover/250/${album.mbid}${album.cover_art_url ? `?fallback=${encodeURIComponent(album.cover_art_url)}` : ""}`
    : (album?.cover_art_url ?? null);
  const loggedDate = new Date(entry.logged_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  const reviewBody = review?.body ?? null;
  const preview =
    reviewBody !== null && reviewBody.length > PREVIEW_CHARS
      ? `${reviewBody.slice(0, PREVIEW_CHARS).trimEnd()}…`
      : reviewBody;

  return (
    <li className="py-6" style={{ borderBottom: "1px solid var(--separator)" }}>
      <article className="flex items-start gap-4">
        <Link
          href={`/album/${encodeURIComponent(entry.album_id)}`}
          className="block shrink-0"
          aria-label={`Open ${album?.title ?? "album"}`}
        >
          {coverUrl ? (
            <img
              src={coverUrl}
              alt=""
              width={72}
              height={72}
              className="size-[72px] rounded object-cover"
              style={{ background: "var(--surface)" }}
            />
          ) : (
            <div
              aria-hidden="true"
              className="size-[72px] rounded"
              style={{ background: "var(--surface)" }}
            />
          )}
        </Link>

        <div className="min-w-0 flex-1">
          {/* Title + year */}
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <Link
              href={`/album/${encodeURIComponent(entry.album_id)}`}
              className="font-serif font-semibold tracking-[-0.01em] hover:underline"
              style={{
                fontSize: "18px",
                color: "var(--foreground)",
                fontFamily: "var(--font-serif)",
              }}
            >
              {album?.title ?? "Unknown album"}
            </Link>
            {album?.release_year != null && (
              <span className="font-mono" style={{ fontSize: "12px", color: "var(--muted)" }}>
                {album.release_year}
              </span>
            )}
          </div>

          {/* Artist */}
          <p className="mt-0.5 truncate font-sans text-[13px]" style={{ color: "var(--muted)" }}>
            {album?.artist_credit ?? entry.album_id}
          </p>

          {/* Metadata row: date · rating · aux · relisten · visibility · edited */}
          <div
            className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono"
            style={{ fontSize: "11px", letterSpacing: "0.04em", color: "var(--muted)" }}
          >
            <span>{loggedDate}</span>
            {entry.rating != null && (
              <span className="inline-flex items-center gap-1.5">
                <span aria-hidden="true" style={{ color: "var(--accent)" }}>
                  <StarRow value={entry.rating} size={12} />
                </span>
                <span className="sr-only">Rated {entry.rating} of 5 stars</span>
              </span>
            )}
            {entry.auxed && (
              <span
                aria-label="Aux’d"
                className="inline-flex items-center gap-1 uppercase"
                style={{ letterSpacing: "0.12em", color: "var(--gold)" }}
              >
                <AuxIcon filled size={11} />
                Aux’d
              </span>
            )}
            {entry.relisten && <span aria-label="Relisten">Relisten</span>}
            {entry.visibility !== "public" && (
              <Badge variant="outline" className="h-4 px-1.5 py-0 text-[10px] uppercase">
                {entry.visibility}
              </Badge>
            )}
            {entry.edited_at && <span title={`edited ${entry.edited_at}`}>Edited</span>}
          </div>

          {/* Review excerpt — Newsreader serif body matching the
              dedicated read view, with markdown rendering. Shown only
              when a review is attached AND the sidecar surfaced its
              body (visibility transitively gated by the parent diary
              entry's visibility). The excerpt is NOT wrapped in a
              `<Link>` — markdown can emit inline `<a>` for `[text](url)`
              and nested anchors are invalid HTML. The "Read more →"
              affordance below is the navigation cue. */}
          {preview !== null && entry.review_id !== null && (
            <>
              <div
                className="mt-3 font-serif [&_p+p]:mt-2 [&_p]:mt-0"
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: "16px",
                  lineHeight: 1.65,
                  letterSpacing: "-0.003em",
                  color: "var(--foreground)",
                  fontOpticalSizing: "auto",
                }}
              >
                {renderReviewBody(preview)}
              </div>
              <Link
                href={`/review/${encodeURIComponent(entry.review_id)}`}
                className="mt-2 inline-block font-mono uppercase hover:underline"
                style={{
                  fontSize: "11px",
                  letterSpacing: "0.12em",
                  color: "var(--muted)",
                }}
              >
                Read full review →
              </Link>
            </>
          )}

          {/* Owner controls */}
          {showOwnerControls && (onEdit || onDelete) && (
            <div
              className="mt-3 flex gap-4 font-mono uppercase"
              style={{ fontSize: "11px", letterSpacing: "0.12em" }}
            >
              {onEdit && (
                <button
                  type="button"
                  onClick={() => onEdit(entry)}
                  className="cursor-pointer hover:underline"
                  style={{ color: "var(--muted)" }}
                >
                  Edit
                </button>
              )}
              {onDelete && (
                <button
                  type="button"
                  onClick={() => onDelete(entry)}
                  className="cursor-pointer hover:underline"
                  style={{ color: "var(--muted)" }}
                >
                  Delete
                </button>
              )}
            </div>
          )}
        </div>
      </article>
    </li>
  );
}
