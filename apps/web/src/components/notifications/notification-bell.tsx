"use client";

import { apiClient } from "@/lib/api-client";
import { type UnreadCountResponse, formatUnreadBadge } from "@/lib/notifications";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import Link from "next/link";

const UNREAD_COUNT_KEY = ["notifications", "unread-count"] as const;

export function NotificationBell() {
  const { data } = useQuery({
    queryKey: UNREAD_COUNT_KEY,
    queryFn: async () => apiClient.get<UnreadCountResponse>("/api/v1/notifications/unread-count"),
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });

  const badgeText = formatUnreadBadge(data?.count ?? 0);

  return (
    <Link
      href="/notifications"
      aria-label={badgeText ? `Notifications (${badgeText} unread)` : "Notifications"}
      className={cn(
        "relative inline-flex h-9 w-9 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
    >
      <Bell className="size-5" aria-hidden="true" />
      {badgeText !== null ? (
        <span
          aria-hidden="true"
          className={cn(
            "absolute -right-0.5 -top-0.5 inline-flex min-w-[1.1rem] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-4 text-destructive-foreground"
          )}
        >
          {badgeText}
        </span>
      ) : null}
    </Link>
  );
}

export const NOTIFICATIONS_UNREAD_COUNT_QUERY_KEY = UNREAD_COUNT_KEY;
