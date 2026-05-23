"use client";

import { CriticBadge } from "@/components/critic-badge";
import { LikeButton } from "@/components/review-card/like-button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import type { Review, ReviewUserCard } from "@/lib/review-types";
import { useAuthStore } from "@/stores/auth";
import Link from "next/link";

const PREVIEW_CHARS = 80;

type Props = {
  review: Review;
  user: ReviewUserCard | undefined;
  /** When true, an "Edit / Delete" overflow appears (T092). */
  showOwnerControls?: boolean;
  onEdit?: (review: Review) => void;
  onDelete?: (review: Review) => void;
};

export function ReviewCard({ review, user, showOwnerControls, onEdit, onDelete }: Props) {
  const viewer = useAuthStore((s) => s.user);
  const initialLiked = viewer != null && review.recent_likers.includes(viewer.id);
  const isOwn = viewer != null && viewer.id === review.user_id;
  const preview =
    review.body.length > PREVIEW_CHARS
      ? `${review.body.slice(0, PREVIEW_CHARS).trimEnd()}…`
      : review.body;

  return (
    <li className="rounded-md border bg-card transition-colors hover:bg-muted/40">
      <Link
        href={`/review/${encodeURIComponent(review.id)}`}
        className="block px-3 py-3"
        aria-label={`Read ${user?.handle ?? "user"}'s full review`}
      >
        <header className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <Avatar className="size-7">
              <AvatarFallback>
                {(user?.handle ?? review.user_id).slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 leading-tight">
              <p className="truncate text-sm font-medium">
                {user?.display_name ?? user?.handle ?? `User ${review.user_id.slice(0, 8)}`}
                <CriticBadge isCritic={user?.is_critic_seed} />
              </p>
              <p className="truncate text-xs text-muted-foreground">@{user?.handle ?? "unknown"}</p>
            </div>
            {review.edited_at && (
              <Badge variant="outline" className="h-5 px-1.5 py-0 text-[10px]">
                edited
              </Badge>
            )}
            {review.visibility !== "public" && (
              <Badge variant="outline" className="h-5 px-1.5 py-0 text-[10px] capitalize">
                {review.visibility}
              </Badge>
            )}
          </div>
          <LikeButton
            reviewId={review.id}
            initialLiked={initialLiked}
            initialCount={review.likes_count}
            disabled={isOwn}
          />
        </header>
        <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">{preview}</p>
        {showOwnerControls && (onEdit || onDelete) && (
          <div className="mt-2 flex gap-3 text-xs">
            {onEdit && (
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onEdit(review);
                }}
                className="text-muted-foreground hover:text-foreground"
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
                className="text-muted-foreground hover:text-destructive"
              >
                Delete
              </button>
            )}
          </div>
        )}
      </Link>
    </li>
  );
}
