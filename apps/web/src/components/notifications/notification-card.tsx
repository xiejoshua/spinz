"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { type NotificationItem, clickUrlFor, copyPartsFor, timeAgo } from "@/lib/notifications";
import { cn } from "@/lib/utils";
import Link from "next/link";

type Props = {
  notification: NotificationItem;
  onActivate?: (notification: NotificationItem) => void;
};

export function NotificationCard({ notification, onActivate }: Props) {
  const parts = copyPartsFor(notification);
  const href = clickUrlFor(notification);
  const isRead = notification.read_at !== null;

  const avatarFallbackChar = (
    notification.actor_handle?.slice(0, 1) ??
    notification.actor_display_name?.slice(0, 1) ??
    "A"
  ).toUpperCase();

  return (
    <Link
      href={href}
      onClick={() => {
        onActivate?.(notification);
      }}
      className={cn(
        "flex w-full items-start gap-3 rounded-md border p-3 text-left transition-colors hover:bg-muted/50",
        isRead ? "bg-background" : "border-foreground/20 bg-muted/30"
      )}
    >
      <Avatar className="size-10 shrink-0">
        {notification.actor_avatar_url ? (
          <AvatarImage src={notification.actor_avatar_url} alt="" />
        ) : null}
        <AvatarFallback>{avatarFallbackChar}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="text-sm leading-snug">
          {parts.actor ? (
            <>
              <strong className="font-medium">{parts.actor}</strong>{" "}
            </>
          ) : null}
          <span>{parts.verb}</span>
          {parts.subject ? (
            <>
              {" "}
              <em className="not-italic font-medium">{parts.subject}</em>
            </>
          ) : null}
          {parts.suffix ? <span className="text-muted-foreground"> {parts.suffix}</span> : null}
        </p>
        <p className="text-xs text-muted-foreground">{timeAgo(notification.created_at)}</p>
      </div>
      {!isRead ? (
        <span
          aria-hidden="true"
          className="mt-1.5 size-2 shrink-0 rounded-full bg-primary"
          title="Unread"
        />
      ) : null}
    </Link>
  );
}
