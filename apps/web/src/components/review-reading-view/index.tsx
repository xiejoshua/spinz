"use client";

import { EditReviewDialog } from "@/components/review-card/edit-review";
import { LikeButton } from "@/components/review-card/like-button";
import { ReadingHero } from "@/components/review-reading-view/hero";
import { ShareButton } from "@/components/review-reading-view/share-button";
import { Button } from "@/components/ui/button";
import type { AlbumPayload, DiaryRow } from "@/lib/album-types";
import type { Review, ReviewUserCard } from "@/lib/review-types";
import { useAuthStore } from "@/stores/auth";
import { Pencil } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

type Props = {
  review: Review;
  user: ReviewUserCard | undefined;
  album: AlbumPayload;
  viewerEntry: DiaryRow | null;
  shareUrl: string;
};

/**
 * Letterboxd-parity reading view for a single review.
 *
 * State variants (handled implicitly via props):
 * - **Owner**  — `useAuthStore().user.id === review.user_id`. Like button
 *   is shown but disabled (TC-016: can't like own review).
 * - **Follower / public** — Like button enabled.
 * - **No rating context** — `viewerEntry === null`. The hero omits the
 *   "You rated this …" line.
 *
 * Comments thread is explicitly NOT in scope (v2 per CR-002).
 */
export function ReviewReadingView({ review, user, album, viewerEntry, shareUrl }: Props) {
  const viewer = useAuthStore((s) => s.user);
  const initialLiked = viewer != null && review.recent_likers.includes(viewer.id);
  const isOwn = viewer != null && viewer.id === review.user_id;
  const [editing, setEditing] = useState(false);

  return (
    <article className="container max-w-2xl space-y-6 px-4 py-6">
      <Link
        href={`/album/${encodeURIComponent(album.id)}`}
        className="inline-block text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to {album.title}
      </Link>
      <ReadingHero review={review} user={user} album={album} viewerEntry={viewerEntry} />
      <div className="prose prose-sm max-w-none whitespace-pre-line leading-relaxed">
        {review.body}
      </div>
      <footer className="flex items-center gap-3 border-t pt-4">
        <LikeButton
          reviewId={review.id}
          initialLiked={initialLiked}
          initialCount={review.likes_count}
          compact={false}
          disabled={isOwn}
        />
        {isOwn && (
          <Button type="button" variant="outline" size="sm" onClick={() => setEditing(true)}>
            <Pencil className="mr-1 size-4" aria-hidden="true" />
            Edit
          </Button>
        )}
        <ShareButton
          url={shareUrl}
          title={`${user?.handle ?? "review"}'s review of ${album.title}`}
        />
      </footer>
      <EditReviewDialog review={editing ? review : null} onClose={() => setEditing(false)} />
    </article>
  );
}
