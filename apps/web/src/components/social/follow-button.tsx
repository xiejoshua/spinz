"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type { FollowMutationResponse, FollowState, ProfileResponse } from "@/lib/social-types";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

type Props = {
  handle: string;
  initialRelation: FollowState;
  initialFollowerCount: number;
  /** Hide the button on self / blocked / anonymous viewers. */
  visible: boolean;
};

const PROFILE_KEY = (handle: string) => ["profile", handle] as const;

export function FollowButton({ handle, initialRelation, initialFollowerCount, visible }: Props) {
  const [confirmUnfollow, setConfirmUnfollow] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const followMutation = useMutation({
    mutationFn: async () =>
      apiClient.post<FollowMutationResponse>(`/api/v1/users/${encodeURIComponent(handle)}/follow`),
    onMutate: () => {
      const prev = queryClient.getQueryData<ProfileResponse>(PROFILE_KEY(handle));
      if (prev) {
        queryClient.setQueryData<ProfileResponse>(PROFILE_KEY(handle), {
          ...prev,
          relation: "following",
          counts: { ...prev.counts, followers: prev.counts.followers + 1 },
        });
      }
      return prev;
    },
    onError: (error, _vars, prev) => {
      if (prev) queryClient.setQueryData(PROFILE_KEY(handle), prev);
      const message =
        error instanceof ApiError
          ? error.status === 400
            ? "You can't follow yourself."
            : error.status === 403
              ? "You can't follow this user."
              : `Follow failed (${error.status}).`
          : "Could not reach the server.";
      toast({ title: "Couldn't follow", description: message });
    },
    onSuccess: (data) => {
      capture("social.follow", { followee_handle: handle, state: data.state });
      if (data.state === "pending") {
        toast({ title: "Request sent", description: "Awaiting approval." });
        queryClient.setQueryData<ProfileResponse>(PROFILE_KEY(handle), (cur) =>
          cur ? { ...cur, relation: "pending" } : cur
        );
      }
      void queryClient.invalidateQueries({ queryKey: PROFILE_KEY(handle) });
    },
  });

  const unfollowMutation = useMutation({
    mutationFn: async () => {
      await apiClient.delete(`/api/v1/users/${encodeURIComponent(handle)}/follow`);
    },
    onMutate: () => {
      const prev = queryClient.getQueryData<ProfileResponse>(PROFILE_KEY(handle));
      if (prev) {
        queryClient.setQueryData<ProfileResponse>(PROFILE_KEY(handle), {
          ...prev,
          relation: "none",
          counts: { ...prev.counts, followers: Math.max(0, prev.counts.followers - 1) },
        });
      }
      return prev;
    },
    onError: (_error, _vars, prev) => {
      if (prev) queryClient.setQueryData(PROFILE_KEY(handle), prev);
      toast({ title: "Couldn't unfollow", description: "Try again in a moment." });
    },
    onSuccess: () => {
      capture("social.unfollow", { followee_handle: handle });
      toast({ title: "Unfollowed" });
      void queryClient.invalidateQueries({ queryKey: PROFILE_KEY(handle) });
    },
  });

  if (!visible) return null;

  // Use the live cache value if it exists; fall back to props for SSR-first paint.
  const live = queryClient.getQueryData<ProfileResponse>(PROFILE_KEY(handle));
  const relation = live?.relation ?? initialRelation;
  const _ = initialFollowerCount; // surfaced for parent UI; not consumed in this button

  if (relation === "self" || relation === "anonymous" || relation === "blocked") {
    return null;
  }

  if (relation === "pending") {
    return (
      <Button variant="outline" disabled>
        Request sent
      </Button>
    );
  }

  if (relation === "following") {
    return (
      <>
        <Button variant="outline" onClick={() => setConfirmUnfollow(true)}>
          Following
        </Button>
        <Dialog
          open={confirmUnfollow}
          onOpenChange={(v) => (v ? setConfirmUnfollow(true) : setConfirmUnfollow(false))}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Unfollow @{handle}?</DialogTitle>
              <DialogDescription>
                You'll stop seeing their logs in your home feed. You can follow again any time.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setConfirmUnfollow(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={unfollowMutation.isPending}
                onClick={() => {
                  setConfirmUnfollow(false);
                  unfollowMutation.mutate();
                }}
              >
                Unfollow
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </>
    );
  }

  return (
    <Button
      disabled={followMutation.isPending}
      onClick={() => {
        followMutation.mutate();
      }}
    >
      {followMutation.isPending ? "Following…" : "Follow"}
    </Button>
  );
}
