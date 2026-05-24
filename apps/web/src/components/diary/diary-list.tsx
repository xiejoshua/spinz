"use client";

import { DeleteConfirmation } from "@/components/diary/delete-confirmation";
import { DiaryEntryCard } from "@/components/diary/diary-entry-card";
import { AuxIcon } from "@/components/icons/aux";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToastAction } from "@/components/ui/toast";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import type { DiaryAlbumCard, DiaryEntry, DiaryListResponse } from "@/lib/diary-types";
import { useUiStore } from "@/stores/ui";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";

type Props = {
  handle: string;
  isOwner: boolean;
};

type Filter = "all" | "auxed";

const PAGE_SIZE = 25;
const UNDO_DURATION_MS = 8000;

function buildPath(handle: string, filter: Filter, cursor: string | null): string {
  const search = new URLSearchParams();
  search.set("limit", String(PAGE_SIZE));
  if (filter === "auxed") search.set("auxed", "true");
  if (cursor) search.set("cursor", cursor);
  return `/api/v1/users/${encodeURIComponent(handle)}/diary?${search.toString()}`;
}

export function DiaryList({ handle, isOwner }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  const [pendingDelete, setPendingDelete] = useState<DiaryEntry | null>(null);
  const openLogSheet = useUiStore((s) => s.openLogSheet);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const query = useInfiniteQuery({
    queryKey: ["diary", handle, filter] as const,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) =>
      apiClient.get<DiaryListResponse>(buildPath(handle, filter, pageParam)),
    getNextPageParam: (last) => last.next_cursor,
  });

  const allAlbums = useMemo(() => {
    const map: Record<string, DiaryAlbumCard> = {};
    for (const page of query.data?.pages ?? []) {
      Object.assign(map, page.albums);
    }
    return map;
  }, [query.data]);

  const handleEdit = useCallback(
    (entry: DiaryEntry) => {
      const album = allAlbums[entry.album_id];
      if (!album) {
        toast({
          title: "Couldn’t open edit",
          description: "Album metadata unavailable — refresh and try again.",
        });
        return;
      }
      openLogSheet({
        album_id: album.id,
        mbid: album.mbid,
        title: album.title,
        artist_credit: album.artist_credit,
        cover_art_url: album.cover_art_url,
        edit: {
          entry_id: entry.id,
          rating: entry.rating,
          auxed: entry.auxed,
          visibility: entry.visibility,
        },
      });
    },
    [allAlbums, openLogSheet, toast]
  );

  const handleDeleteConfirmed = useCallback(
    async (entry: DiaryEntry) => {
      setPendingDelete(null);
      try {
        await apiClient.delete(`/api/v1/diary/entries/${encodeURIComponent(entry.id)}`);
      } catch (error) {
        const message =
          error instanceof ApiError
            ? error.status === 410
              ? "Already deleted."
              : error.status === 403
                ? "You can only delete your own entries."
                : `Delete failed (${error.status}).`
            : "Could not reach the server.";
        toast({ title: "Delete failed", description: message });
        return;
      }
      await queryClient.invalidateQueries({ queryKey: ["diary", handle] });

      let undone = false;
      const undo = async () => {
        if (undone) return;
        undone = true;
        try {
          await apiClient.post(`/api/v1/diary/entries/${encodeURIComponent(entry.id)}/restore`);
          await queryClient.invalidateQueries({ queryKey: ["diary", handle] });
          toast({ title: "Restored", description: "Entry restored." });
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
        description: "Your diary entry was removed.",
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

  if (query.isLoading) {
    return <div className="py-6 text-center text-sm text-muted-foreground">Loading diary…</div>;
  }
  if (query.isError) {
    return (
      <div className="py-6 text-center text-sm text-destructive">
        Could not load diary.{" "}
        <button
          type="button"
          className="underline"
          onClick={() => {
            void query.refetch();
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  const entries = (query.data?.pages ?? []).flatMap((page) => page.entries);

  return (
    <div className="space-y-4">
      <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="auxed">Aux’d</TabsTrigger>
        </TabsList>
        {/* Empty TabsContent panels keep Radix's aria-controls valid
         * (T171). See feed-list.tsx for the same fix + rationale. */}
        <TabsContent value="all" className="sr-only" />
        <TabsContent value="auxed" className="sr-only" />
      </Tabs>
      {entries.length === 0 ? (
        <EmptyState filter={filter} isOwner={isOwner} />
      ) : (
        <ul className="space-y-2">
          {entries.map((entry) => (
            <DiaryEntryCard
              key={entry.id}
              entry={entry}
              album={allAlbums[entry.album_id]}
              showOwnerControls={isOwner}
              onEdit={isOwner ? handleEdit : undefined}
              onDelete={isOwner ? setPendingDelete : undefined}
            />
          ))}
        </ul>
      )}
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
      <DeleteConfirmation
        entry={pendingDelete}
        onCancel={() => setPendingDelete(null)}
        onConfirm={handleDeleteConfirmed}
      />
    </div>
  );
}

function EmptyState({ filter, isOwner }: { filter: Filter; isOwner: boolean }) {
  let body: React.ReactNode;
  if (filter === "auxed") {
    body = isOwner ? (
      <>
        Nothing aux’d yet — flip the{" "}
        <span
          aria-hidden="true"
          className="inline-flex items-center align-text-bottom"
          style={{ color: "var(--gold)" }}
        >
          <AuxIcon filled size={14} />
        </span>{" "}
        toggle when you log a standout.
      </>
    ) : (
      "No aux’d albums yet."
    );
  } else {
    body = isOwner
      ? "Your diary is empty — log your first album to get started."
      : "No public diary entries yet.";
  }
  return (
    <p className="rounded-md border border-dashed bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
      {body}
    </p>
  );
}
