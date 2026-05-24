"use client";

import { CriticBadge } from "@/components/critic-badge";
import { AuxIcon } from "@/components/icons/aux";
import { LikeIcon } from "@/components/icons/like";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import type { DiaryAlbumCard } from "@/lib/diary-types";
import type { FeedEntry, FeedReviewSnippet } from "@/lib/feed-types";
import type { ReviewUserCard } from "@/lib/review-types";
import Link from "next/link";

type Props = {
  entry: FeedEntry;
  user: ReviewUserCard | undefined;
  album: DiaryAlbumCard | undefined;
  review: FeedReviewSnippet | undefined;
};

export function FeedEntryCard({ entry, user, album, review }: Props) {
  const coverUrl = album?.mbid
    ? `/api/cover/250/${album.mbid}${album.cover_art_url ? `?fallback=${encodeURIComponent(album.cover_art_url)}` : ""}`
    : (album?.cover_art_url ?? null);
  const loggedDate = new Date(entry.logged_at).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
  return (
    <li className="rounded-md border bg-card px-3 py-3">
      <div className="flex items-start gap-3">
        <Link
          href={`/album/${encodeURIComponent(entry.album_id)}`}
          className="block shrink-0"
          aria-label={`Open ${album?.title ?? "album"}`}
        >
          {coverUrl ? (
            <img
              src={coverUrl}
              alt=""
              width={64}
              height={64}
              loading="lazy"
              className="size-16 rounded bg-muted object-cover"
            />
          ) : (
            <div aria-hidden="true" className="size-16 rounded bg-muted" />
          )}
        </Link>
        <div className="min-w-0 flex-1 space-y-1">
          <header className="flex items-center gap-2">
            <Avatar className="size-6">
              <AvatarFallback>
                {(user?.handle ?? entry.user_id).slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <Link
              href={`/profile/${encodeURIComponent(user?.handle ?? "")}`}
              className="truncate text-sm font-medium hover:underline"
            >
              {user?.display_name ?? user?.handle ?? `User ${entry.user_id.slice(0, 8)}`}
              <CriticBadge isCritic={user?.is_critic_seed} />
            </Link>
            <span className="text-xs text-muted-foreground">{loggedDate}</span>
          </header>
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <Link
              href={`/album/${encodeURIComponent(entry.album_id)}`}
              className="truncate text-sm font-medium hover:underline"
            >
              {album?.title ?? "Unknown album"}
            </Link>
            {album?.release_year != null && (
              <span className="text-xs text-muted-foreground">{album.release_year}</span>
            )}
          </div>
          <p className="truncate text-xs text-muted-foreground">
            {album?.artist_credit ?? entry.album_id}
          </p>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {entry.rating != null && (
              <span>
                <span aria-hidden="true" className="text-foreground">
                  {"★".repeat(Math.round(entry.rating))}
                </span>
                <span className="sr-only">Rated {entry.rating} of 5 stars</span>
              </span>
            )}
            {entry.auxed && (
              <Badge variant="secondary" className="h-5 px-1.5 py-0">
                <span
                  aria-hidden="true"
                  className="mr-1 inline-flex items-center"
                  style={{ color: "var(--gold)" }}
                >
                  <AuxIcon filled size={12} />
                </span>
                Aux’d
              </Badge>
            )}
            {entry.review_id && (
              <Link
                href={`/review/${encodeURIComponent(entry.review_id)}`}
                className="text-muted-foreground hover:underline"
              >
                review ·{" "}
                <span
                  aria-hidden="true"
                  className="inline-flex items-center align-text-bottom"
                >
                  <LikeIcon filled size={12} />
                </span>{" "}
                {review?.likes_count ?? 0}
              </Link>
            )}
            {entry.score_components?.source === "critic_seed_padding" && (
              <Badge variant="outline" className="h-5 px-1.5 py-0 text-[10px]">
                critic pick
              </Badge>
            )}
          </div>
          {review?.body_preview && (
            <p className="line-clamp-2 pt-1 text-sm text-muted-foreground">{review.body_preview}</p>
          )}
        </div>
      </div>
    </li>
  );
}
