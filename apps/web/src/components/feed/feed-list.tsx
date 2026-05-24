"use client";

import { FeedEntryCard } from "@/components/feed/feed-entry";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiClient } from "@/lib/api-client";
import type { DiaryAlbumCard } from "@/lib/diary-types";
import type { FeedListResponse, FeedMode, FeedReviewSnippet } from "@/lib/feed-types";
import type { ReviewUserCard } from "@/lib/review-types";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

const PAGE_SIZE = 25;

function buildPath(mode: FeedMode, cursor: string | null): string {
  const search = new URLSearchParams();
  search.set("mode", mode);
  search.set("limit", String(PAGE_SIZE));
  if (cursor) search.set("cursor", cursor);
  return `/api/v1/feed?${search.toString()}`;
}

export function FeedList() {
  const [mode, setMode] = useState<FeedMode>("for_you");

  const query = useInfiniteQuery({
    queryKey: ["feed", mode] as const,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => apiClient.get<FeedListResponse>(buildPath(mode, pageParam)),
    getNextPageParam: (last) => last.next_cursor,
  });

  const { users, albums, reviews } = useMemo(() => {
    const u: Record<string, ReviewUserCard> = {};
    const a: Record<string, DiaryAlbumCard> = {};
    const r: Record<string, FeedReviewSnippet> = {};
    for (const page of query.data?.pages ?? []) {
      Object.assign(u, page.users);
      Object.assign(a, page.albums);
      Object.assign(r, page.reviews);
    }
    return { users: u, albums: a, reviews: r };
  }, [query.data]);

  const entries = (query.data?.pages ?? []).flatMap((page) => page.entries);

  return (
    <div className="space-y-4">
      <Tabs value={mode} onValueChange={(v) => setMode(v as FeedMode)}>
        <TabsList>
          <TabsTrigger value="for_you">For You</TabsTrigger>
          <TabsTrigger value="latest">Latest</TabsTrigger>
        </TabsList>
        {/*
         * Both panels reference the same feed list below — the value of
         * `mode` drives the actual data fetch. We render empty TabsContent
         * elements so Radix's aria-controls wiring resolves to real DOM
         * nodes (T171 a11y audit). Without this the trigger's aria-controls
         * points at an id that doesn't exist, which axe-core flags as a
         * CRITICAL aria-valid-attr-value violation.
         */}
        <TabsContent value="for_you" className="sr-only" />
        <TabsContent value="latest" className="sr-only" />
      </Tabs>
      {query.isLoading ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Loading feed…</p>
      ) : query.isError ? (
        <p className="py-6 text-center text-sm text-destructive">
          Could not load feed.{" "}
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
      ) : entries.length === 0 ? (
        <p className="rounded-md border border-dashed bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
          Nothing yet — follow a few critics or friends to fill your feed.
        </p>
      ) : (
        <>
          <ul className="space-y-2">
            {entries.map((entry) => (
              <FeedEntryCard
                key={entry.id}
                entry={entry}
                user={users[entry.user_id]}
                album={albums[entry.album_id]}
                review={entry.review_id ? reviews[entry.review_id] : undefined}
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
                {query.isFetchingNextPage ? "Loading…" : "Load more"}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
