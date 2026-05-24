"use client";

import { CriticBadge } from "@/components/critic-badge";
import { StarRow } from "@/components/icons/star-row";
import { LikeButton } from "@/components/review-card/like-button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { renderReviewBody } from "@/lib/review-body";
import type { Review, ReviewAlbumCard, ReviewUserCard } from "@/lib/review-types";
import { useAuthStore } from "@/stores/auth";
import Link from "next/link";

const PREVIEW_CHARS = 140;

type Props = {
  review: Review;
  user: ReviewUserCard | undefined;
  /** Optional album sidecar (passed on the profile reviews list, omitted on
   * the album-detail reviews list where the parent album is implicit). */
  album?: ReviewAlbumCard;
  showOwnerControls?: boolean;
  onEdit?: (review: Review) => void;
  onDelete?: (review: Review) => void;
};

/**
 * Editorial review card — matches the example-feed pattern from the
 * landing: avatar + serif headline (album title when present) + mono
 * @handle + body preview + Like / Edit / Delete affordances. No card
 * border or background — sits on the page's --background with a
 * hairline separator between siblings (rendered by the parent list).
 */
export function ReviewCard({ review, user, album, showOwnerControls, onEdit, onDelete }: Props) {
  const viewer = useAuthStore((s) => s.user);
  const initialLiked = viewer != null && review.recent_likers.includes(viewer.id);
  const isOwn = viewer != null && viewer.id === review.user_id;
  const preview =
    review.body.length > PREVIEW_CHARS
      ? `${review.body.slice(0, PREVIEW_CHARS).trimEnd()}…`
      : review.body;

  const displayName = user?.display_name ?? user?.handle ?? `User ${review.user_id.slice(0, 8)}`;
  const handle = user?.handle ?? "unknown";

  const coverUrl = album?.mbid
    ? `/api/cover/250/${album.mbid}${album.cover_art_url ? `?fallback=${encodeURIComponent(album.cover_art_url)}` : ""}`
    : (album?.cover_art_url ?? null);

  return (
    <li className="py-6" style={{ borderBottom: "1px solid var(--separator)" }}>
      <Link
        href={`/review/${encodeURIComponent(review.id)}`}
        className="block"
        aria-label={`Read ${handle}'s full review`}
      >
        <article className="flex gap-4">
          <Avatar className="size-10 shrink-0">
            <AvatarFallback>
              <span
                className="font-serif text-[14px] font-semibold"
                style={{
                  color: "var(--foreground)",
                  fontFamily: "var(--font-serif)",
                }}
              >
                {handle.slice(0, 2).toUpperCase()}
              </span>
            </AvatarFallback>
          </Avatar>

          <div className="min-w-0 flex-1">
            {/* Author row */}
            <header
              className="flex flex-wrap items-baseline gap-x-2 font-sans text-[14px]"
              style={{ color: "var(--foreground)" }}
            >
              <span className="font-semibold">{displayName}</span>
              <CriticBadge isCritic={user?.is_critic_seed} />
              <span className="font-mono text-[12px]" style={{ color: "var(--muted)" }}>
                @{handle}
              </span>
              {review.edited_at && (
                <span
                  className="font-mono uppercase"
                  style={{
                    fontSize: "10px",
                    letterSpacing: "0.15em",
                    color: "var(--muted)",
                  }}
                >
                  · edited
                </span>
              )}
              {review.visibility !== "public" && (
                <span
                  className="font-mono uppercase"
                  style={{
                    fontSize: "10px",
                    letterSpacing: "0.15em",
                    color: "var(--muted)",
                  }}
                >
                  · {review.visibility}
                </span>
              )}
            </header>

            {/* Rating row — author's rating from the joined DiaryEntry.
                Mirrors the landing example feed's star line. */}
            {review.rating != null && review.rating > 0 && (
              <div
                className="mt-2 inline-flex items-center gap-1.5"
                style={{ color: "var(--accent)" }}
              >
                <StarRow value={review.rating} size={14} />
                <span
                  className="font-mono tabular-nums"
                  style={{ fontSize: "11px", color: "var(--muted)" }}
                >
                  {review.rating.toFixed(1)}
                </span>
              </div>
            )}

            {/* Album row (only on profile reviews; omitted on album-detail) */}
            {album && (
              <div className="mt-3 flex items-center gap-3">
                {coverUrl ? (
                  <img
                    src={coverUrl}
                    alt=""
                    width={48}
                    height={48}
                    className="size-12 shrink-0 rounded object-cover"
                    style={{ background: "var(--surface-secondary)" }}
                  />
                ) : (
                  <div
                    aria-hidden
                    className="size-12 shrink-0 rounded"
                    style={{
                      background:
                        "linear-gradient(135deg, var(--surface-secondary), var(--surface-tertiary))",
                    }}
                  />
                )}
                <div className="min-w-0">
                  <div
                    className="truncate font-serif font-semibold leading-tight tracking-[-0.005em]"
                    style={{
                      fontSize: "17px",
                      color: "var(--foreground)",
                      fontFamily: "var(--font-serif)",
                    }}
                  >
                    {album.title}
                  </div>
                  <div
                    className="mt-0.5 truncate font-sans text-[12px]"
                    style={{ color: "var(--muted)" }}
                  >
                    {album.artist_credit}
                    {album.release_year ? ` · ${album.release_year}` : ""}
                  </div>
                </div>
              </div>
            )}

            {/* Body preview — markdown rendering mirrors the backend
                sanitization allowlist (bold / italic / inline links).
                Truncation happens BEFORE rendering, which means a body
                that ends mid-emphasis renders the trailing markers as
                literal text. Acceptable for a preview; full read view
                gets the real markup. */}
            <div
              className="mt-3 font-serif [&_p+p]:mt-2 [&_p]:mt-0"
              style={{
                color: "var(--foreground)",
                fontFamily: "var(--font-serif)",
                fontSize: "16px",
                lineHeight: 1.65,
                fontOpticalSizing: "auto",
              }}
            >
              {renderReviewBody(preview)}
            </div>

            {/* Footer — Like + owner controls */}
            <footer className="mt-3 flex items-center gap-4">
              <LikeButton
                reviewId={review.id}
                initialLiked={initialLiked}
                initialCount={review.likes_count}
                disabled={isOwn}
              />
              {showOwnerControls && (onEdit || onDelete) && (
                <>
                  {onEdit && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onEdit(review);
                      }}
                      className="font-mono uppercase hover:underline"
                      style={{
                        fontSize: "10px",
                        letterSpacing: "0.15em",
                        color: "var(--muted)",
                      }}
                    >
                      Edit
                    </button>
                  )}
                  {onDelete && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onDelete(review);
                      }}
                      className="font-mono uppercase hover:underline"
                      style={{
                        fontSize: "10px",
                        letterSpacing: "0.15em",
                        color: "var(--muted)",
                      }}
                    >
                      Delete
                    </button>
                  )}
                </>
              )}
            </footer>
          </div>
        </article>
      </Link>
    </li>
  );
}
