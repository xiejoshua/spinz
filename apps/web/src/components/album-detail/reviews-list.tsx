"use client";

import { ReviewSortSelect } from "@/components/album-detail/review-sort-select";
import { ReviewCard } from "@/components/review-card";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import type { ReviewUserCard, ReviewsListResponse } from "@/lib/review-types";
import { useUiStore } from "@/stores/ui";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useMemo } from "react";

type Props = {
  albumId: string;
};

const PAGE_SIZE = 25;

function buildPath(albumId: string, sort: string, cursor: string | null): string {
  const search = new URLSearchParams();
  search.set("sort", sort);
  search.set("limit", String(PAGE_SIZE));
  if (cursor) search.set("cursor", cursor);
  return `/api/v1/albums/${encodeURIComponent(albumId)}/reviews?${search.toString()}`;
}

export function ReviewsList({ albumId }: Props) {
  const sort = useUiStore((s) => s.feedSort);

  const query = useInfiniteQuery({
    queryKey: ["reviews", albumId, sort] as const,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) =>
      apiClient.get<ReviewsListResponse>(buildPath(albumId, sort, pageParam)),
    getNextPageParam: (last) => last.next_cursor,
  });

  const users = useMemo(() => {
    const map: Record<string, ReviewUserCard> = {};
    for (const page of query.data?.pages ?? []) {
      Object.assign(map, page.users);
    }
    return map;
  }, [query.data]);

  const reviews = (query.data?.pages ?? []).flatMap((page) => page.reviews);

  return (
    <section aria-labelledby="reviews-heading" className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 id="reviews-heading" className="text-lg font-semibold">
          Reviews
        </h2>
        <ReviewSortSelect />
      </div>
      {query.isLoading ? (
        <p className="py-4 text-center text-sm text-muted-foreground">Loading reviews…</p>
      ) : query.isError ? (
        <p className="py-4 text-center text-sm text-destructive">
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
        <p className="rounded-md border border-dashed bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
          No reviews yet — be the first to write one.
        </p>
      ) : (
        <>
          <ul className="space-y-2">
            {reviews.map((review) => (
              <ReviewCard key={review.id} review={review} user={users[review.user_id]} />
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
    </section>
  );
}
