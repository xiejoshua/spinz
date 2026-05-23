"use client";

import { Button } from "@/components/ui/button";
import { SortableBacklogItem } from "@/components/up-next/sortable-item";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import type { BacklogItem, BacklogListResponse } from "@/lib/backlog-types";
import type { DiaryAlbumCard } from "@/lib/diary-types";
import { capture } from "@/lib/posthog";
import {
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

const PAGE_SIZE = 25;
const LIST_KEY = ["backlog", "list"] as const;

function buildPath(cursor: string | null): string {
  const search = new URLSearchParams();
  search.set("limit", String(PAGE_SIZE));
  if (cursor) search.set("cursor", cursor);
  return `/api/v1/users/me/backlog/items?${search.toString()}`;
}

export function UpNextList() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [localOrder, setLocalOrder] = useState<BacklogItem[] | null>(null);

  const query = useInfiniteQuery({
    queryKey: LIST_KEY,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => apiClient.get<BacklogListResponse>(buildPath(pageParam)),
    getNextPageParam: (last) => last.next_cursor,
  });

  const allAlbums = useMemo(() => {
    const map: Record<string, DiaryAlbumCard> = {};
    for (const page of query.data?.pages ?? []) {
      Object.assign(map, page.albums);
    }
    return map;
  }, [query.data]);

  const serverItems = useMemo(
    () => (query.data?.pages ?? []).flatMap((page) => page.items),
    [query.data]
  );

  // Reset local order whenever the server resyncs (e.g. on remove or add).
  // The dep on ``query.dataUpdatedAt`` is the explicit "server refetched"
  // signal — Biome's exhaustive-deps doesn't see it as load-bearing here
  // because the effect body doesn't reference it, but that is precisely
  // the intent.
  // biome-ignore lint/correctness/useExhaustiveDependencies: dataUpdatedAt is the deliberate refetch trigger
  useEffect(() => {
    setLocalOrder(null);
  }, [query.dataUpdatedAt]);

  const items = localOrder ?? serverItems;

  const reorderMutation = useMutation({
    mutationFn: async (itemIds: string[]) =>
      apiClient.patch<{ items: BacklogItem[] }>("/api/v1/users/me/backlog/items/reorder", {
        item_ids: itemIds,
      }),
    onSuccess: () => {
      capture("backlog.reordered");
      void queryClient.invalidateQueries({ queryKey: LIST_KEY });
    },
    onError: (error) => {
      setLocalOrder(null);
      const message =
        error instanceof ApiError && error.status === 422
          ? "Order didn't match the server. Refreshing."
          : "Could not reach the server.";
      toast({ title: "Reorder failed", description: message });
    },
  });

  const removeMutation = useMutation({
    mutationFn: async (item: BacklogItem) => {
      await apiClient.delete(`/api/v1/users/me/backlog/items/${encodeURIComponent(item.id)}`);
      return item;
    },
    onSuccess: (item) => {
      capture("backlog.item_removed", { album_id: item.album_id, source: "up_next" });
      toast({ title: "Removed from Up Next" });
      void queryClient.invalidateQueries({ queryKey: LIST_KEY });
      void queryClient.invalidateQueries({
        queryKey: ["backlog", "contains", item.album_id],
      });
    },
    onError: () => {
      toast({ title: "Couldn't remove", description: "Try again in a moment." });
    },
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((i) => i.id === active.id);
    const newIndex = items.findIndex((i) => i.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const next = arrayMove(items, oldIndex, newIndex);
    setLocalOrder(next);
    reorderMutation.mutate(next.map((i) => i.id));
  }

  if (query.isLoading) {
    return <p className="py-6 text-center text-sm text-muted-foreground">Loading…</p>;
  }
  if (query.isError) {
    return (
      <p className="py-6 text-center text-sm text-destructive">
        Could not load Up Next.{" "}
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
    );
  }
  if (items.length === 0) {
    return (
      <p className="rounded-md border border-dashed bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
        Up Next is empty — add an album from its detail page or right after logging.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
          <ul className="space-y-2">
            {items.map((item) => (
              <SortableBacklogItem
                key={item.id}
                item={item}
                album={allAlbums[item.album_id]}
                onRemove={(toRemove) => removeMutation.mutate(toRemove)}
              />
            ))}
          </ul>
        </SortableContext>
      </DndContext>
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
    </div>
  );
}
