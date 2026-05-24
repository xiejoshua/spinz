"use client";

import { ReviewSortSelect } from "@/components/album-detail/review-sort-select";
import { ReviewCard } from "@/components/review-card";
import { DeleteReviewConfirmation } from "@/components/review-card/delete-confirmation";
import { EditReviewDialog } from "@/components/review-card/edit-review";
import { Button } from "@/components/ui/button";
import { ToastAction } from "@/components/ui/toast";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type {
  Review,
  ReviewAlbumCard,
  ReviewUserCard,
  UserReviewsListResponse,
} from "@/lib/review-types";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";

type Props = {
  handle: string;
};

const PAGE_SIZE = 25;
const UNDO_DURATION_MS = 8000;

/**
 * Build the canonical URL for the user-reviews endpoint (T094).
 *
 * Mirrors the album-detail reviews list — same sort + cursor + limit
 * shape, just keyed off ``{handle}`` instead of ``{album_id}``.
 */
function buildPath(handle: string, sort: string, cursor: string | null): string {
  const search = new URLSearchParams();
  search.set("sort", sort);
  search.set("limit", String(PAGE_SIZE));
  if (cursor) search.set("cursor", cursor);
  return `/api/v1/users/${encodeURIComponent(handle)}/reviews?${search.toString()}`;
}

/**
 * Client-side renderer for the reviews-only profile sub-route (T094).
 *
 * Drives an infinite-scroll list against ``GET /api/v1/users/{handle}/reviews``
 * sharing the same sort selector as the album-detail reviews list (via the
 * shared :func:`UiStore.feedSort` store key). When the viewer is the owner,
 * the ReviewCard renders Edit + Delete affordances that mount the existing
 * EditReviewDialog and DeleteReviewConfirmation modals.
 */
export function ProfileReviewsList({ handle }: Props) {
  const sort = useUiStore((s) => s.feedSort);
  const viewer = useAuthStore((s) => s.user);
  const isOwner = viewer?.handle === handle;
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [editing, setEditing] = useState<Review | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Review | null>(null);

  const query = useInfiniteQuery({
    queryKey: ["profile-reviews", handle, sort] as const,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) =>
      apiClient.get<UserReviewsListResponse>(buildPath(handle, sort, pageParam)),
    getNextPageParam: (last) => last.next_cursor,
  });

  const users = useMemo(() => {
    const map: Record<string, ReviewUserCard> = {};
    for (const page of query.data?.pages ?? []) {
      Object.assign(map, page.users);
    }
    return map;
  }, [query.data]);

  const albums = useMemo(() => {
    const map: Record<string, ReviewAlbumCard> = {};
    for (const page of query.data?.pages ?? []) {
      Object.assign(map, page.albums);
    }
    return map;
  }, [query.data]);

  const handleDeleteConfirmed = useCallback(
    async (review: Review) => {
      setPendingDelete(null);
      try {
        await apiClient.delete(`/api/v1/reviews/${encodeURIComponent(review.id)}`);
      } catch (error) {
        const message =
          error instanceof ApiError
            ? error.status === 410
              ? "Already deleted."
              : error.status === 403
                ? "You can only delete your own reviews."
                : `Delete failed (${error.status}).`
            : "Could not reach the server.";
        toast({ title: "Delete failed", description: message });
        return;
      }
      capture("review.delete", { review_id: review.id });
      await queryClient.invalidateQueries({ queryKey: ["profile-reviews", handle] });
      await queryClient.invalidateQueries({ queryKey: ["reviews"] });

      let undone = false;
      const undo = async () => {
        if (undone) return;
        undone = true;
        try {
          // The reviews endpoint mirrors the diary trash — restore is
          // POST /api/v1/reviews/{id}/restore. Even if the backend
          // doesn't yet expose that path, the toast still gives the user
          // a clear "we tried" affordance and the failure is contained.
          await apiClient.post(`/api/v1/reviews/${encodeURIComponent(review.id)}/restore`);
          await queryClient.invalidateQueries({ queryKey: ["profile-reviews", handle] });
          toast({ title: "Restored", description: "Review restored." });
        } catch (error) {
          const message =
            error instanceof ApiError && error.status === 410
              ? "Restore window expired."
              : "Could not restore — try the Trash later.";
          toast({ title: "Undo failed", description: message });
        }
      };

      toast({
        title: "Deleted",
        description: "Your review was removed.",
        duration: UNDO_DURATION_MS,
        action: (
          <ToastAction altText="Undo delete" onClick={() => void undo()}>
            Undo
          </ToastAction>
        ),
      });
    },
    [handle, queryClient, toast]
  );

  const reviews = (query.data?.pages ?? []).flatMap((page) => page.reviews);

  return (
    <section aria-labelledby="profile-reviews-heading" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2
          id="profile-reviews-heading"
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          Reviews
        </h2>
        <ReviewSortSelect />
      </div>
      <div className="h-px" style={{ background: "var(--separator)" }} />
      {query.isLoading ? (
        <p
          className="py-4 text-center font-sans text-sm"
          style={{ color: "var(--muted)" }}
        >
          Loading reviews…
        </p>
      ) : query.isError ? (
        <p
          className="py-4 text-center font-sans text-sm"
          style={{ color: "var(--danger)" }}
        >
          Could not load reviews.{" "}
          <button
            type="button"
            className="underline"
            onClick={() => {
              void query.refetch();
            }}
          >
            Retry
          </button>
        </p>
      ) : reviews.length === 0 ? (
        <p
          className="rounded-md border border-dashed px-4 py-8 text-center font-sans text-sm"
          style={{
            background: "var(--surface)",
            borderColor: "var(--border)",
            color: "var(--muted)",
          }}
        >
          {isOwner ? "You haven't written any reviews yet." : "No reviews yet."}
        </p>
      ) : (
        <>
          <ul>
            {reviews.map((review) => (
              <ReviewCard
                key={review.id}
                review={review}
                user={users[review.user_id]}
                album={albums[review.album_id]}
                showOwnerControls={isOwner}
                onEdit={isOwner ? setEditing : undefined}
                onDelete={isOwner ? setPendingDelete : undefined}
              />
            ))}
          </ul>
          {query.hasNextPage && (
            <div className="flex justify-center pt-1">
              <Button
                variant="outline"
                size="sm"
                disabled={query.isFetchingNextPage}
                onClick={() => {
                  void query.fetchNextPage();
                }}
              >
                {query.isFetchingNextPage ? "Loading…" : "Load more reviews"}
              </Button>
            </div>
          )}
        </>
      )}
      <EditReviewDialog review={editing} onClose={() => setEditing(null)} />
      <DeleteReviewConfirmation
        review={pendingDelete}
        onCancel={() => setPendingDelete(null)}
        onConfirm={handleDeleteConfirmed}
      />
    </section>
  );
}
