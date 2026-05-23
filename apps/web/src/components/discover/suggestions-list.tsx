"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type {
  FollowMutationResponse,
  SuggestionEntry,
  SuggestionsResponse,
} from "@/lib/social-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import Link from "next/link";

const KEY = ["suggestions"] as const;

const REASON_LABELS: Record<string, string> = {
  mutual_taste: "Mutual taste",
  followed_by_followed: "Followed by people you follow",
  shared_seed: "Shares a critic with you",
  label_genre: "Similar taste in genres",
  recency: "Recently active",
};

function formatReasons(reasons: string[]): string {
  if (reasons.length === 0) return "Suggested for you";
  return reasons.map((r) => REASON_LABELS[r] ?? r).join(" · ");
}

export function SuggestionsList() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const query = useQuery({
    queryKey: KEY,
    queryFn: async () =>
      apiClient.get<SuggestionsResponse>("/api/v1/users/me/suggestions?limit=10"),
    staleTime: 60_000,
  });

  const followMutation = useMutation({
    mutationFn: async (s: SuggestionEntry) =>
      apiClient.post<FollowMutationResponse>(
        `/api/v1/users/${encodeURIComponent(s.user.handle)}/follow`
      ),
    onSuccess: (data, s) => {
      capture("social.follow", { followee_handle: s.user.handle, source: "discover" });
      toast({
        title: data.state === "pending" ? "Request sent" : `Following @${s.user.handle}`,
      });
      void queryClient.invalidateQueries({ queryKey: KEY });
    },
    onError: (error, s) => {
      const message =
        error instanceof ApiError
          ? error.status === 403
            ? "You can't follow this user."
            : `Follow failed (${error.status}).`
          : "Could not reach the server.";
      toast({ title: `Couldn't follow @${s.user.handle}`, description: message });
    },
  });

  const dismissMutation = useMutation({
    mutationFn: async (s: SuggestionEntry) => {
      await apiClient.post(`/api/v1/users/me/suggestions/${encodeURIComponent(s.user.id)}/dismiss`);
    },
    onSuccess: (_data, s) => {
      capture("social.suggestion_dismissed", { suggested_user_id: s.user.id });
      // Optimistically prune.
      queryClient.setQueryData<SuggestionsResponse>(KEY, (cur) =>
        cur ? { ...cur, suggestions: cur.suggestions.filter((x) => x.user.id !== s.user.id) } : cur
      );
    },
    onError: () => {
      toast({ title: "Couldn't dismiss", description: "Try again in a moment." });
    },
  });

  if (query.isLoading) {
    return <p className="py-6 text-center text-sm text-muted-foreground">Loading suggestions…</p>;
  }
  if (query.isError) {
    return (
      <p className="py-6 text-center text-sm text-destructive">
        Could not load suggestions.{" "}
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

  const suggestions = query.data?.suggestions ?? [];
  if (suggestions.length === 0) {
    return (
      <p className="rounded-md border border-dashed bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
        No suggestions yet — log a few albums and follow some critics to seed the algorithm.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {suggestions.map((s) => (
        <li key={s.user.id} className="flex items-center gap-3 rounded-md border bg-card px-3 py-3">
          <Avatar className="size-10">
            <AvatarFallback>{s.user.handle.slice(0, 2).toUpperCase()}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1 leading-tight">
            <Link
              href={`/profile/${encodeURIComponent(s.user.handle)}`}
              className="block truncate text-sm font-medium hover:underline"
            >
              {s.user.display_name ?? s.user.handle}
            </Link>
            <p className="truncate text-xs text-muted-foreground">@{s.user.handle}</p>
            <p className="truncate pt-1 text-xs text-muted-foreground">
              {formatReasons(s.reasons)}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button
              size="sm"
              disabled={followMutation.isPending}
              onClick={() => {
                followMutation.mutate(s);
              }}
            >
              Follow
            </Button>
            <button
              type="button"
              aria-label="Dismiss suggestion"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={() => {
                dismissMutation.mutate(s);
              }}
            >
              <X aria-hidden="true" className="size-4" />
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
