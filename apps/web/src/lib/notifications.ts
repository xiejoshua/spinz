// Shared types + helpers for the notifications surface (T139 + T140 + T141).
//
// The backend types are exposed via @auxd/shared-types (api.ts), but the UI
// is mostly easier to write against narrow domain types — so we keep the
// shapes here and verify alignment via the integration tests on the backend
// side. The string union for ``type`` mirrors NotificationType.value exactly.

export type NotificationKind =
  | "follow.new"
  | "follow.request_pending"
  | "follow.request_approved"
  | "review.liked"
  | "review.reply"
  | "friend.logged_album"
  | "friend.high_rated"
  | "weekly.digest"
  | "import.completed"
  | "import.failed"
  | "report.acknowledged"
  | "account.deletion_scheduled"
  | "account.deletion_reminder_7d"
  | "system.announcement"
  | "security.new_session"
  | "security.password_changed";

export type NotificationItem = {
  id: string;
  type: NotificationKind;
  payload: Record<string, unknown>;
  actor_id: string | null;
  actor_handle: string | null;
  actor_display_name: string | null;
  actor_avatar_url: string | null;
  /** T152 — true when the actor is an active CriticSeed account. */
  actor_is_critic_seed?: boolean;
  read_at: string | null;
  created_at: string;
  coalesced_count: number;
};

export type NotificationsListResponse = {
  notifications: NotificationItem[];
  next_cursor: string | null;
};

export type UnreadCountResponse = {
  count: number;
};

export type NotificationPreferences = {
  in_app: Record<string, boolean>;
  email: Record<string, boolean>;
  push: Record<string, boolean>;
  weekly_digest: boolean;
  quiet_hours: {
    enabled: boolean;
    start: string | null;
    end: string | null;
    tz: string;
  };
};

// ---------------------------------------------------------------------------
// Click-through router — mirrors the backend web_push._click_url_for shape.
// ---------------------------------------------------------------------------

export function clickUrlFor(notif: NotificationItem, viewerHandle?: string): string {
  const payload = notif.payload;
  switch (notif.type) {
    case "review.liked":
    case "review.reply": {
      const reviewId = payload.review_id;
      if (typeof reviewId === "string" && reviewId.length > 0) {
        return `/review/${encodeURIComponent(reviewId)}`;
      }
      return "/";
    }
    case "follow.new":
    case "follow.request_pending":
    case "follow.request_approved": {
      const handle = notif.actor_handle ?? (payload.actor_handle as string | undefined);
      if (handle) return `/profile/${encodeURIComponent(handle)}`;
      return "/";
    }
    case "friend.logged_album":
    case "friend.high_rated": {
      const albumId = payload.album_id;
      if (typeof albumId === "string" && albumId.length > 0) {
        return `/album/${encodeURIComponent(albumId)}`;
      }
      return "/";
    }
    case "weekly.digest": {
      const url = payload.summary_url;
      if (typeof url === "string" && url.length > 0) return url;
      return "/";
    }
    case "report.acknowledged":
      return viewerHandle
        ? `/profile/${encodeURIComponent(viewerHandle)}/settings/notifications`
        : "/";
    case "account.deletion_scheduled":
    case "account.deletion_reminder_7d":
      return viewerHandle ? `/profile/${encodeURIComponent(viewerHandle)}/settings/data` : "/";
    case "security.new_session":
    case "security.password_changed":
      return viewerHandle ? `/profile/${encodeURIComponent(viewerHandle)}/settings` : "/";
    case "system.announcement": {
      const link = payload.link;
      if (typeof link === "string" && link.length > 0) return link;
      return "/";
    }
    case "import.completed":
    case "import.failed":
      // v2 — kept for forward-compat. No active surface at MVP.
      return "/";
    default:
      return "/";
  }
}

// ---------------------------------------------------------------------------
// Per-type copy renderer.
//
// Returns a plain-text title for a row. The list component wraps strong /
// em accents inline; keeping the copy as text here keeps the renderer
// trivially unit-testable.
// ---------------------------------------------------------------------------

export type CopyParts = {
  /** The leading actor handle, if applicable. */
  actor?: string;
  /** Verb / action phrase. */
  verb: string;
  /** Optional subject (album title, etc). */
  subject?: string;
  /** Optional trailing suffix. */
  suffix?: string;
};

function actorLabel(notif: NotificationItem): string | undefined {
  if (notif.actor_handle) return `@${notif.actor_handle}`;
  if (notif.actor_display_name) return notif.actor_display_name;
  const payloadHandle = notif.payload.actor_handle;
  if (typeof payloadHandle === "string" && payloadHandle.length > 0) {
    return `@${payloadHandle}`;
  }
  return undefined;
}

function payloadString(value: unknown): string | undefined {
  if (typeof value === "string" && value.length > 0) return value;
  return undefined;
}

export function copyPartsFor(notif: NotificationItem): CopyParts {
  const actor = actorLabel(notif);

  if (notif.coalesced_count > 1) {
    return {
      actor,
      verb: `and ${notif.coalesced_count - 1} other${
        notif.coalesced_count - 1 === 1 ? "" : "s"
      } posted new updates`,
    };
  }

  switch (notif.type) {
    case "follow.new":
      return { actor, verb: "followed you" };
    case "follow.request_pending":
      return { actor, verb: "requested to follow you" };
    case "follow.request_approved":
      return { actor, verb: "approved your follow request" };
    case "review.liked": {
      const title = payloadString(notif.payload.album_title);
      return {
        actor,
        verb: "liked your review",
        subject: title ? `of ${title}` : undefined,
      };
    }
    case "review.reply":
      return { actor, verb: "replied to your review" };
    case "friend.logged_album": {
      const title = payloadString(notif.payload.album_title);
      return {
        actor,
        verb: "logged",
        subject: title,
        suffix: "from your Up Next",
      };
    }
    case "friend.high_rated": {
      const title = payloadString(notif.payload.album_title);
      const rating = notif.payload.rating;
      const stars = typeof rating === "number" ? `${rating.toFixed(1)}★` : undefined;
      return {
        actor,
        verb: "rated",
        subject: title,
        suffix: stars,
      };
    }
    case "weekly.digest":
      return { verb: "Your weekly digest is here" };
    case "report.acknowledged":
      return { verb: "A report you filed has been reviewed" };
    case "account.deletion_scheduled":
      return { verb: "Your account is scheduled for deletion" };
    case "account.deletion_reminder_7d":
      return { verb: "Your account will be deleted in 7 days" };
    case "security.new_session":
      return { verb: "New sign-in to your auxd account" };
    case "security.password_changed":
      return { verb: "Your password was changed" };
    case "system.announcement": {
      const title = payloadString(notif.payload.title);
      return { verb: title ?? "Announcement from auxd" };
    }
    case "import.completed":
      return { verb: "Your import is ready" };
    case "import.failed":
      return { verb: "Your import did not complete" };
    default:
      return { verb: "New notification" };
  }
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

/**
 * Cap unread badge display at 99 → "99+". Anything <= 0 returns null so the
 * caller can hide the badge entirely.
 */
export function formatUnreadBadge(count: number): string | null {
  if (count <= 0) return null;
  if (count > 99) return "99+";
  return String(count);
}

/**
 * Short relative-time helper. Returns "just now", "Xm", "Xh", "Xd", "Xw",
 * or an absolute "MMM d, YYYY" string for older entries. Locale-agnostic
 * by design — accurate enough for an inbox badge, not for invoices.
 */
export function timeAgo(isoTimestamp: string, now: Date = new Date()): string {
  const then = new Date(isoTimestamp);
  if (Number.isNaN(then.getTime())) return "";
  const diffMs = now.getTime() - then.getTime();
  if (diffMs < 0) return "just now";
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w`;
  return then.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
