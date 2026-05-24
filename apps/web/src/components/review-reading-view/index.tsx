"use client";

import { EditReviewDialog } from "@/components/review-card/edit-review";
import { LikeButton } from "@/components/review-card/like-button";
import { ReadingHero } from "@/components/review-reading-view/hero";
import { ShareButton } from "@/components/review-reading-view/share-button";
import { Button } from "@/components/ui/button";
import type { AlbumPayload, DiaryRow } from "@/lib/album-types";
import { renderReviewBody } from "@/lib/review-body";
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
 * Editorial article-frame for a single review (Phase 5).
 *
 *   - Newsreader 32-48px headline on the album title
 *   - 65ch reading column (typographic optimum, ~Pitchfork / The Quietus)
 *   - ::first-letter drop-cap on the first paragraph of body
 *   - Small-caps "edited" tag, no chip
 *   - Sticky Like affordance bottom-right on mobile, inline on desktop
 *
 * State variants (handled implicitly via props):
 *   - Owner    — Like disabled (TC-016: can't like own review). Edit shown.
 *   - Follower / public — Like enabled.
 *   - No rating context — hero omits the rating row.
 *
 * Comments thread is explicitly NOT in scope (v2 per CR-002).
 */
export function ReviewReadingView({ review, user, album, viewerEntry, shareUrl }: Props) {
  const viewer = useAuthStore((s) => s.user);
  const initialLiked = viewer != null && review.recent_likers.includes(viewer.id);
  const isOwn = viewer != null && viewer.id === review.user_id;
  const [editing, setEditing] = useState(false);

  return (
    <article className="mx-auto max-w-[65ch] px-6 py-10">
      <Link
        href={`/album/${encodeURIComponent(album.id)}`}
        className="mb-8 inline-block font-sans text-[13px] hover:underline"
        style={{ color: "var(--muted)" }}
      >
        ← Back to {album.title}
      </Link>

      <ReadingHero review={review} user={user} album={album} viewerEntry={viewerEntry} />

      {/* Body — editorial article frame. */}
      {(() => {
        // Drop-cap is reserved for essay-length bodies. A one-sentence
        // review reads awkwardly with a giant first letter, so we gate
        // on body length (>= 240 chars) AND at least one paragraph
        // break, which together pick up actual essays without applying
        // to short reactions.
        const eligibleForDropCap = review.body.length >= 240 && review.body.includes("\n\n");
        return (
          <>
            <div
              className={`review-body mt-10 font-serif${eligibleForDropCap ? " review-body--drop-cap" : ""}`}
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: "19px",
                lineHeight: 1.65,
                letterSpacing: "-0.003em",
                color: "var(--foreground)",
                fontOpticalSizing: "auto",
              }}
            >
              {renderReviewBody(review.body)}
            </div>
            {/* Drop-cap matches the body font family (Newsreader) so the
                first letter reads as a heavier, larger version of the
                same serif — true editorial cue. Paragraphs are real
                `<p>` elements (markdown renderer), so the `::first-letter`
                selector lands on the first paragraph cleanly. */}
            <style>{`
              .review-body p + p { margin-top: 1.25em; }
              .review-body--drop-cap p:first-of-type::first-letter {
                float: left;
                font-family: inherit;
                font-size: 3.4em;
                line-height: 0.86;
                font-weight: 600;
                padding-right: 0.08em;
                padding-top: 0.02em;
                color: var(--foreground);
              }
            `}</style>
          </>
        );
      })()}

      <footer
        className="mt-12 flex flex-wrap items-center gap-3 pt-6"
        style={{ borderTop: "1px solid var(--separator)" }}
      >
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
