"use client";

import { NOTIFICATIONS_UNREAD_COUNT_QUERY_KEY } from "@/components/notifications/notification-bell";
import { NotificationCard } from "@/components/notifications/notification-card";
import { PushPrompt } from "@/components/notifications/push-prompt";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import type { NotificationItem, NotificationsListResponse } from "@/lib/notifications";
import { capture } from "@/lib/posthog";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const NOTIFICATIONS_LIST_KEY = ["notifications", "list"] as const;

export function NotificationList() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const query = useInfiniteQuery({
    queryKey: NOTIFICATIONS_LIST_KEY,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const params = pageParam ? `?cursor=${encodeURIComponent(pageParam)}` : "";
      return apiClient.get<NotificationsListResponse>(`/api/v1/notifications${params}`);
    },
    getNextPageParam: (last) => last.next_cursor,
  });

  const markReadMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post<{ ok: true }>(`/api/v1/notifications/${encodeURIComponent(id)}/read`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_LIST_KEY });
      void queryClient.invalidateQueries({
        queryKey: NOTIFICATIONS_UNREAD_COUNT_QUERY_KEY,
      });
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: async () =>
      apiClient.post<{ ok: true; marked: number }>("/api/v1/notifications/mark-all-read"),
    onSuccess: (data) => {
      capture("notifications.mark_all_read", { marked: data.marked });
      toast({
        title: data.marked > 0 ? "All caught up" : "Nothing to mark",
        description:
          data.marked > 0
            ? `Marked ${data.marked} notification${data.marked === 1 ? "" : "s"} as read.`
            : undefined,
      });
      void queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_LIST_KEY });
      void queryClient.invalidateQueries({
        queryKey: NOTIFICATIONS_UNREAD_COUNT_QUERY_KEY,
      });
    },
    onError: (err) => {
      const description =
        err instanceof ApiError ? `Server returned ${err.status}.` : "Try again in a moment.";
      toast({ title: "Couldn't mark all as read", description });
    },
  });

  function handleActivate(notification: NotificationItem) {
    if (notification.read_at === null) {
      markReadMutation.mutate(notification.id);
    }
    capture("notifications.opened", {
      type: notification.type,
      had_unread: notification.read_at === null,
    });
  }

  if (query.isLoading) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Loading notifications…</p>;
  }
  if (query.isError) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive">Couldn't load notifications.</p>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            void query.refetch();
          }}
        >
          Retry
        </Button>
      </div>
    );
  }

  const items = (query.data?.pages ?? []).flatMap((page) => page.notifications);

  if (items.length === 0) {
    return (
      <div className="space-y-4">
        <PushPrompt />
        <div className="rounded-md border border-dashed bg-muted/20 p-8 text-center">
          <p className="text-sm font-medium">You're all caught up</p>
          <p className="mt-1 text-xs text-muted-foreground">
            New activity from people you follow will show up here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">{items.length} recent</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={markAllReadMutation.isPending}
          onClick={() => markAllReadMutation.mutate()}
        >
          {markAllReadMutation.isPending ? "Marking…" : "Mark all as read"}
        </Button>
      </div>
      <PushPrompt />
      <ul className="space-y-2">
        {items.map((notification) => (
          <li key={notification.id}>
            <NotificationCard notification={notification} onActivate={handleActivate} />
          </li>
        ))}
      </ul>
      {query.hasNextPage ? (
        <div className="flex justify-center pt-2">
          <Button
            type="button"
            variant="outline"
            disabled={query.isFetchingNextPage}
            onClick={() => {
              void query.fetchNextPage();
            }}
          >
            {query.isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export { NOTIFICATIONS_LIST_KEY };
