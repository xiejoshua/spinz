"use client";

import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import type { BacklogContainsResponse, BacklogItem } from "@/lib/backlog-types";
import { capture } from "@/lib/posthog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, BookmarkCheck } from "lucide-react";

type Props = {
  albumId: string;
};

export function UpNextButton({ albumId }: Props) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const containsQuery = useQuery({
    queryKey: ["backlog", "contains", albumId] as const,
    queryFn: async () =>
      apiClient.get<BacklogContainsResponse>(
        `/api/v1/users/me/backlog/contains?album_id=${encodeURIComponent(albumId)}`
      ),
    staleTime: 30_000,
  });

  const inBacklog = containsQuery.data?.in_backlog ?? false;
  const itemId = containsQuery.data?.item_id ?? null;

  const addMutation = useMutation({
    mutationFn: async () =>
      apiClient.post<BacklogItem>("/api/v1/users/me/backlog/items", { album_id: albumId }),
    onSuccess: (item) => {
      capture("backlog.item_added", { album_id: albumId, source: "album_detail" });
      queryClient.setQueryData<BacklogContainsResponse>(["backlog", "contains", albumId], {
        in_backlog: true,
        item_id: item.id,
      });
      void queryClient.invalidateQueries({ queryKey: ["backlog", "list"] });
      toast({ title: "Added to Up Next", description: "We'll keep it queued for you." });
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.status === 409
            ? "Already in your Up Next."
            : error.status === 401
              ? "Sign in to use Up Next."
              : `Add failed (${error.status}).`
          : "Could not reach the server.";
      toast({ title: "Couldn't add", description: message });
    },
  });

  const removeMutation = useMutation({
    mutationFn: async () => {
      if (!itemId) return;
      await apiClient.delete(`/api/v1/users/me/backlog/items/${encodeURIComponent(itemId)}`);
    },
    onSuccess: () => {
      capture("backlog.item_removed", { album_id: albumId, source: "album_detail" });
      queryClient.setQueryData<BacklogContainsResponse>(["backlog", "contains", albumId], {
        in_backlog: false,
        item_id: null,
      });
      void queryClient.invalidateQueries({ queryKey: ["backlog", "list"] });
      toast({ title: "Removed from Up Next" });
    },
    onError: (error) => {
      const message =
        error instanceof ApiError && error.status === 404
          ? "Already removed."
          : "Could not reach the server.";
      toast({ title: "Couldn't remove", description: message });
    },
  });

  const pending = addMutation.isPending || removeMutation.isPending || containsQuery.isLoading;

  return (
    <Button
      variant="outline"
      disabled={pending}
      aria-pressed={inBacklog}
      onClick={() => {
        if (inBacklog) removeMutation.mutate();
        else addMutation.mutate();
      }}
    >
      {inBacklog ? (
        <>
          <BookmarkCheck className="mr-1 size-4" aria-hidden="true" />
          On Up Next
        </>
      ) : (
        <>
          <Bookmark className="mr-1 size-4" aria-hidden="true" />
          Add to Up Next
        </>
      )}
    </Button>
  );
}
