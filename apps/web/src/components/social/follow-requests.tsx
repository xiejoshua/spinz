"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import { timeAgo } from "@/lib/notifications";
import { capture } from "@/lib/posthog";
import type { FollowRequestsListResponse } from "@/lib/social-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const QUERY_KEY = ["follow-requests", "pending"] as const;

export function FollowRequestsInbox() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () =>
      apiClient.get<FollowRequestsListResponse>("/api/v1/users/me/follow-requests"),
    staleTime: 15_000,
  });

  const approveMutation = useMutation({
    mutationFn: async (requestId: string) =>
      apiClient.post(`/api/v1/users/me/follow-requests/${requestId}/approve`),
    onSuccess: (_data, requestId) => {
      toast({ title: "Follow request approved" });
      capture("follow_request.approved", { request_id: requestId });
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast({
          title: "Could not approve",
          description: error.statusText,
          variant: "destructive",
        });
      }
    },
  });

  const declineMutation = useMutation({
    mutationFn: async (requestId: string) =>
      apiClient.post(`/api/v1/users/me/follow-requests/${requestId}/decline`),
    onSuccess: (_data, requestId) => {
      toast({ title: "Follow request declined" });
      capture("follow_request.declined", { request_id: requestId });
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast({
          title: "Could not decline",
          description: error.statusText,
          variant: "destructive",
        });
      }
    },
  });

  const requests = query.data?.requests ?? [];
  const users = query.data?.users ?? {};

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-medium">Pending follow requests</h3>
      {query.isLoading ? (
        <p className="text-xs text-muted-foreground">Loading…</p>
      ) : requests.length === 0 ? (
        <p className="rounded-md border bg-muted/40 p-4 text-sm text-muted-foreground">
          No pending follow requests.
        </p>
      ) : (
        <ul className="space-y-2">
          {requests.map((request) => {
            const requester = users[request.requester_id];
            const isBusy =
              (approveMutation.isPending && approveMutation.variables === request.id) ||
              (declineMutation.isPending && declineMutation.variables === request.id);
            const initials = (requester?.handle ?? request.requester_id).slice(0, 2).toUpperCase();
            return (
              <li
                key={request.id}
                className="flex items-center justify-between gap-3 rounded-md border p-3"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <Avatar className="size-9">
                    {requester?.avatar_url ? (
                      <AvatarImage src={requester.avatar_url} alt="" />
                    ) : null}
                    <AvatarFallback>{initials}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 leading-tight">
                    <p className="truncate text-sm font-medium">
                      {requester?.display_name ?? requester?.handle ?? "Unknown user"}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      @{requester?.handle ?? "unknown"} · {timeAgo(request.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => declineMutation.mutate(request.id)}
                    disabled={isBusy}
                  >
                    Decline
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => approveMutation.mutate(request.id)}
                    disabled={isBusy}
                  >
                    Approve
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
