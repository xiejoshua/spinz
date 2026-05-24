import {
  type NotificationItem,
  clickUrlFor,
  copyPartsFor,
  formatUnreadBadge,
  timeAgo,
} from "@/lib/notifications";
import { describe, expect, it } from "vitest";

function makeItem(overrides: Partial<NotificationItem> = {}): NotificationItem {
  return {
    id: "notif-1",
    type: "follow.new",
    payload: { actor_handle: "alice" },
    actor_id: "user-actor",
    actor_handle: "alice",
    actor_display_name: "Alice",
    actor_avatar_url: null,
    read_at: null,
    created_at: new Date(Date.now() - 3 * 60_000).toISOString(),
    coalesced_count: 0,
    ...overrides,
  };
}

describe("copyPartsFor", () => {
  it("renders follow.new with actor handle", () => {
    const parts = copyPartsFor(makeItem());
    expect(parts.actor).toBe("@alice");
    expect(parts.verb).toBe("followed you");
  });

  it("renders follow.request_pending", () => {
    const parts = copyPartsFor(makeItem({ type: "follow.request_pending" }));
    expect(parts.verb).toBe("requested to follow you");
  });

  it("renders review.liked with album subject", () => {
    const parts = copyPartsFor(
      makeItem({
        type: "review.liked",
        payload: { album_title: "Channel Orange", review_id: "rev-1" },
      })
    );
    expect(parts.verb).toBe("liked your review");
    expect(parts.subject).toBe("of Channel Orange");
  });

  it("renders friend.logged_album with Up Next suffix", () => {
    const parts = copyPartsFor(
      makeItem({
        type: "friend.logged_album",
        payload: { album_title: "Blonde", album_id: "alb-1" },
      })
    );
    expect(parts.subject).toBe("Blonde");
    expect(parts.suffix).toBe("from your Up Next");
  });

  it("renders friend.high_rated with star suffix", () => {
    const parts = copyPartsFor(
      makeItem({
        type: "friend.high_rated",
        payload: { album_title: "DAMN.", rating: 4.5, album_id: "alb-2" },
      })
    );
    expect(parts.suffix).toBe("4.5★");
  });

  it("renders weekly.digest as a system message (no actor)", () => {
    const parts = copyPartsFor(
      makeItem({
        type: "weekly.digest",
        actor_handle: null,
        actor_display_name: null,
        actor_id: null,
        payload: { summary_url: "https://auxd.fm/d/x", hero_count: 3 },
      })
    );
    expect(parts.actor).toBeUndefined();
    expect(parts.verb).toBe("Your weekly digest is here");
  });

  it("renders report.acknowledged with system copy", () => {
    const parts = copyPartsFor(makeItem({ type: "report.acknowledged" }));
    expect(parts.verb).toBe("A report you filed has been reviewed");
  });

  it("renders security.new_session with stock copy", () => {
    const parts = copyPartsFor(makeItem({ type: "security.new_session" }));
    expect(parts.verb).toBe("New sign-in to your auxd account");
  });

  it("renders coalesced rollup copy", () => {
    const parts = copyPartsFor(makeItem({ coalesced_count: 4 }));
    expect(parts.verb).toMatch(/and 3 others/);
  });

  it("falls back to payload actor_handle when actor fields are null", () => {
    const parts = copyPartsFor(
      makeItem({
        actor_handle: null,
        actor_display_name: null,
        payload: { actor_handle: "fallback" },
      })
    );
    expect(parts.actor).toBe("@fallback");
  });
});

describe("clickUrlFor", () => {
  it("routes review.liked to /review/{id}", () => {
    const url = clickUrlFor(makeItem({ type: "review.liked", payload: { review_id: "rev-42" } }));
    expect(url).toBe("/review/rev-42");
  });

  it("routes follow.new to /profile/{handle}", () => {
    const url = clickUrlFor(makeItem({ type: "follow.new" }));
    expect(url).toBe("/profile/alice");
  });

  it("routes friend.logged_album to /album/{id}", () => {
    const url = clickUrlFor(
      makeItem({
        type: "friend.logged_album",
        payload: { album_id: "alb-1" },
      })
    );
    expect(url).toBe("/album/alb-1");
  });

  it("routes weekly.digest to the summary url when present", () => {
    const url = clickUrlFor(
      makeItem({
        type: "weekly.digest",
        payload: { summary_url: "https://auxd.fm/d/abc" },
      })
    );
    expect(url).toBe("https://auxd.fm/d/abc");
  });

  it("falls back to / when payload key is missing", () => {
    const url = clickUrlFor(
      makeItem({
        type: "review.liked",
        actor_handle: null,
        payload: {},
      })
    );
    expect(url).toBe("/");
  });

  it("routes account.deletion_scheduled to /profile/{handle}/settings/data", () => {
    const url = clickUrlFor(makeItem({ type: "account.deletion_scheduled" }), "bob");
    expect(url).toBe("/profile/bob/settings/data");
  });

  it("falls back to / for account.deletion_scheduled when viewer handle is unknown", () => {
    const url = clickUrlFor(makeItem({ type: "account.deletion_scheduled" }));
    expect(url).toBe("/");
  });
});

describe("formatUnreadBadge", () => {
  it("returns null for 0", () => {
    expect(formatUnreadBadge(0)).toBeNull();
  });

  it("returns 1 for 1", () => {
    expect(formatUnreadBadge(1)).toBe("1");
  });

  it("returns 99 for 99", () => {
    expect(formatUnreadBadge(99)).toBe("99");
  });

  it("returns 99+ for 100", () => {
    expect(formatUnreadBadge(100)).toBe("99+");
  });

  it("returns null for negative", () => {
    expect(formatUnreadBadge(-3)).toBeNull();
  });
});

describe("timeAgo", () => {
  it("returns 'just now' for very recent", () => {
    const now = new Date("2026-01-01T00:00:30Z");
    const ts = new Date("2026-01-01T00:00:00Z").toISOString();
    expect(timeAgo(ts, now)).toBe("just now");
  });

  it("returns minutes for sub-hour", () => {
    const now = new Date("2026-01-01T01:00:00Z");
    const ts = new Date("2026-01-01T00:45:00Z").toISOString();
    expect(timeAgo(ts, now)).toBe("15m");
  });

  it("returns hours for sub-day", () => {
    const now = new Date("2026-01-01T05:00:00Z");
    const ts = new Date("2026-01-01T01:00:00Z").toISOString();
    expect(timeAgo(ts, now)).toBe("4h");
  });

  it("returns days for sub-week", () => {
    const now = new Date("2026-01-05T00:00:00Z");
    const ts = new Date("2026-01-02T00:00:00Z").toISOString();
    expect(timeAgo(ts, now)).toBe("3d");
  });

  it("returns weeks for sub-month", () => {
    const now = new Date("2026-01-22T00:00:00Z");
    const ts = new Date("2026-01-01T00:00:00Z").toISOString();
    expect(timeAgo(ts, now)).toBe("3w");
  });

  it("returns absolute date for older", () => {
    const now = new Date("2026-06-01T12:00:00Z");
    const ts = new Date("2026-02-15T12:00:00Z").toISOString();
    // Locale-dependent formatting — the timestamp falls firmly in Feb
    // 2026 across all common timezones, so a year-fragment match is safe.
    const formatted = timeAgo(ts, now);
    expect(formatted).toMatch(/Feb/);
    expect(formatted).toMatch(/2026/);
  });
});
