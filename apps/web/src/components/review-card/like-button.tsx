"use client";

import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type { ReviewLikeResponse } from "@/lib/review-types";
import { cn } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Heart } from "lucide-react";
import type { MouseEvent } from "react";
import { useState } from "react";

type Props = {
  reviewId: string;
  initialLiked: boolean;
  initialCount: number;
  /** When true, renders compact (icon + count); when false, also shows a label. */
  compact?: boolean;
  /** Disable when the viewer is the reviewer (TC-016 — can't like own review). */
  disabled?: boolean;
};

/**
 * Optimistic like toggle for a review. The viewer-has-liked state is
 * derived heuristically from the parent's `recent_likers` array (only
 * the last ~10 likers are tracked server-side) so the first click after
 * a long gap may show "Like" when the server already records a like —
 * the POST is idempotent and the server response heals the UI.
 */
export function LikeButton({
  reviewId,
  initialLiked,
  initialCount,
  compact = true,
  disabled = false,
}: Props) {
  const [liked, setLiked] = useState(initialLiked);
  const [count, setCount] = useState(initialCount);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const mutation = useMutation({
    mutationFn: async (nextLiked: boolean): Promise<ReviewLikeResponse> => {
      const path = `/api/v1/reviews/${encodeURIComponent(reviewId)}/like`;
      if (nextLiked) return apiClient.post<ReviewLikeResponse>(path);
      return apiClient.delete<ReviewLikeResponse>(path);
    },
    onMutate: (nextLiked) => {
      const prev = { liked, count };
      setLiked(nextLiked);
      setCount((c) => Math.max(0, c + (nextLiked ? 1 : -1)));
      return prev;
    },
    onError: (error, _nextLiked, prev) => {
      if (prev) {
        setLiked(prev.liked);
        setCount(prev.count);
      }
      const message =
        error instanceof ApiError
          ? error.status === 400
            ? "You can't like your own review."
            : error.status === 404
              ? "Review not found."
              : `Like failed (${error.status}).`
          : "Could not reach the server.";
      toast({ title: "Couldn't like", description: message });
    },
    onSuccess: (data) => {
      setLiked(data.liked);
      setCount(data.likes_count);
      capture("review.like", { review_id: reviewId, liked: data.liked });
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
    },
  });

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    // Like button lives inside tap-to-navigate cards (T090 spec): stop the
    // outer link from intercepting.
    event.stopPropagation();
    event.preventDefault();
    if (disabled || mutation.isPending) return;
    mutation.mutate(!liked);
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || mutation.isPending}
      aria-pressed={liked}
      aria-label={liked ? "Unlike review" : "Like review"}
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-sm transition-colors",
        liked ? "text-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
        disabled && "cursor-not-allowed opacity-60"
      )}
    >
      <Heart aria-hidden="true" className={cn("size-4", liked && "fill-current")} />
      <span className="tabular-nums">{count}</span>
      {!compact && <span className="ml-1">{liked ? "Liked" : "Like"}</span>}
    </button>
  );
}
