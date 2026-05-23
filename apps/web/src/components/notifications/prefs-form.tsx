"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { ApiError, apiClient } from "@/lib/api-client";
import type { NotificationPreferences } from "@/lib/notifications";
import { capture } from "@/lib/posthog";
import { cn } from "@/lib/utils";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Settings UI grouping — mirrors notification-taxonomy.md lines 65-91.
// ---------------------------------------------------------------------------

type TypeRow = {
  key: string;
  label: string;
  hint?: string;
  channels: {
    in_app: { available: boolean; locked: boolean; default: boolean };
    email: { available: boolean; locked: boolean; default: boolean };
    push: { available: boolean; locked: boolean; default: boolean };
  };
};

type Group = {
  id: string;
  label: string;
  rows: TypeRow[];
};

// Each row encodes the per-channel availability + lock + default from the
// taxonomy doc. ``locked: true`` means the switch is rendered disabled
// (and we never PUT the locked value to the backend, since the backend
// would reject it). ``available: false`` means the channel does not
// support this type at all (no push for digest, etc) — we render a
// dash instead of a switch.
const GROUPS: Group[] = [
  {
    id: "activity",
    label: "Activity",
    rows: [
      {
        key: "follow.new",
        label: "Follow notifications",
        channels: {
          in_app: { available: true, locked: false, default: true },
          email: { available: true, locked: false, default: false },
          push: { available: true, locked: false, default: true },
        },
      },
      {
        key: "follow.request_pending",
        label: "Follow request pending",
        channels: {
          in_app: { available: true, locked: false, default: true },
          email: { available: true, locked: false, default: false },
          push: { available: true, locked: false, default: true },
        },
      },
      {
        key: "follow.request_approved",
        label: "Follow request approved",
        channels: {
          in_app: { available: true, locked: false, default: true },
          email: { available: true, locked: false, default: false },
          push: { available: false, locked: false, default: false },
        },
      },
      {
        key: "review.liked",
        label: "Review likes",
        channels: {
          in_app: { available: true, locked: false, default: true },
          email: { available: true, locked: false, default: false },
          push: { available: false, locked: false, default: false },
        },
      },
      {
        key: "friend.logged_album",
        label: "Friend logged my Up Next",
        channels: {
          in_app: { available: true, locked: false, default: true },
          email: { available: true, locked: false, default: false },
          push: { available: false, locked: false, default: false },
        },
      },
      {
        key: "friend.high_rated",
        label: "Friend high-rated discovery",
        hint: "Opt-in. Surface ≥4.5★ albums from people you follow.",
        channels: {
          in_app: { available: true, locked: false, default: false },
          email: { available: true, locked: false, default: false },
          push: { available: false, locked: false, default: false },
        },
      },
    ],
  },
  {
    id: "digests",
    label: "Digests",
    rows: [
      {
        key: "weekly.digest",
        label: "Weekly digest",
        hint: "Monday morning summary of your follow graph.",
        channels: {
          in_app: { available: false, locked: false, default: false },
          email: { available: true, locked: false, default: true },
          push: { available: false, locked: false, default: false },
        },
      },
    ],
  },
  {
    id: "account",
    label: "Account & system",
    rows: [
      {
        key: "system.announcement",
        label: "auxd news",
        hint: "Founder-issued product updates. Sent sparingly.",
        channels: {
          in_app: { available: true, locked: false, default: false },
          email: { available: true, locked: false, default: false },
          push: { available: false, locked: false, default: false },
        },
      },
      {
        key: "security.new_session",
        label: "Security: new sign-in",
        hint: "Email always on for your account safety.",
        channels: {
          in_app: { available: true, locked: false, default: true },
          email: { available: true, locked: true, default: true },
          push: { available: false, locked: false, default: false },
        },
      },
      {
        key: "security.password_changed",
        label: "Security: password changed",
        hint: "Email always on for your account safety.",
        channels: {
          in_app: { available: true, locked: false, default: true },
          email: { available: true, locked: true, default: true },
          push: { available: false, locked: false, default: false },
        },
      },
    ],
  },
];

const PREFS_QUERY_KEY = ["notifications", "preferences"] as const;

type Channel = "in_app" | "email" | "push";

function emptyPrefs(): NotificationPreferences {
  return {
    in_app: {},
    email: {},
    push: {},
    weekly_digest: true,
    quiet_hours: { enabled: false, start: null, end: null, tz: "UTC" },
  };
}

function resolveChannel(prefs: NotificationPreferences, channel: Channel, row: TypeRow): boolean {
  const ch = row.channels[channel];
  if (!ch.available) return false;
  if (ch.locked) return true;
  const stored = prefs[channel][row.key];
  if (typeof stored === "boolean") return stored;
  return ch.default;
}

function setChannel(
  prefs: NotificationPreferences,
  channel: Channel,
  row: TypeRow,
  value: boolean
): NotificationPreferences {
  const next: NotificationPreferences = {
    ...prefs,
    [channel]: { ...prefs[channel], [row.key]: value },
  };
  // weekly_digest is the legacy explicit flag in the embedded subdoc — mirror
  // its state from the email channel of N-008 so old consumers keep working.
  if (row.key === "weekly.digest" && channel === "email") {
    next.weekly_digest = value;
  }
  return next;
}

function muteAll(prefs: NotificationPreferences, channel: Channel): NotificationPreferences {
  const next = { ...prefs[channel] };
  for (const group of GROUPS) {
    for (const row of group.rows) {
      const ch = row.channels[channel];
      if (!ch.available || ch.locked) continue;
      next[row.key] = false;
    }
  }
  const result: NotificationPreferences = { ...prefs, [channel]: next };
  if (channel === "email") result.weekly_digest = false;
  return result;
}

function buildDiff(
  initial: NotificationPreferences,
  current: NotificationPreferences
): Record<string, unknown> {
  const diff: Record<string, unknown> = {};
  const channels: Channel[] = ["in_app", "email", "push"];
  for (const channel of channels) {
    const changed: Record<string, boolean> = {};
    const keys = new Set([...Object.keys(initial[channel]), ...Object.keys(current[channel])]);
    for (const key of keys) {
      if (initial[channel][key] !== current[channel][key]) {
        changed[key] = current[channel][key];
      }
    }
    if (Object.keys(changed).length > 0) {
      diff[channel] = changed;
    }
  }
  if (initial.weekly_digest !== current.weekly_digest) {
    diff.weekly_digest = current.weekly_digest;
  }
  if (JSON.stringify(initial.quiet_hours) !== JSON.stringify(current.quiet_hours)) {
    diff.quiet_hours = current.quiet_hours;
  }
  return diff;
}

// ---------------------------------------------------------------------------
// Timezone select — a small curated list plus the browser's resolved tz so
// the user has an obvious correct option without a 400-row dropdown.
// ---------------------------------------------------------------------------

const CURATED_TZS = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Australia/Sydney",
];

function getBrowserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

function buildTimezoneOptions(currentValue: string): string[] {
  const browserTz = getBrowserTimezone();
  const merged = new Set<string>([currentValue, browserTz, ...CURATED_TZS]);
  return Array.from(merged);
}

// ---------------------------------------------------------------------------
// Form component
// ---------------------------------------------------------------------------

export function NotificationPrefsForm() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: PREFS_QUERY_KEY,
    queryFn: async () =>
      apiClient.get<NotificationPreferences>("/api/v1/users/me/notification-preferences"),
  });

  const [prefs, setPrefs] = useState<NotificationPreferences>(emptyPrefs);
  const [initialPrefs, setInitialPrefs] = useState<NotificationPreferences>(emptyPrefs);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (query.data) {
      setPrefs(query.data);
      setInitialPrefs(query.data);
    }
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: async (next: NotificationPreferences) =>
      apiClient.put<NotificationPreferences>("/api/v1/users/me/notification-preferences", next),
    onSuccess: (data, vars) => {
      const diff = buildDiff(initialPrefs, vars);
      capture("settings.notifications_updated", diff);
      setInitialPrefs(data);
      setPrefs(data);
      queryClient.setQueryData(PREFS_QUERY_KEY, data);
      setFormError(null);
      toast({ title: "Notification preferences saved" });
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        const detail = err.detail;
        if (detail && typeof detail === "object" && "detail" in detail) {
          const inner = (detail as { detail: unknown }).detail;
          if (
            inner &&
            typeof inner === "object" &&
            "error" in inner &&
            "message" in inner &&
            typeof (inner as { message: unknown }).message === "string"
          ) {
            setFormError((inner as { message: string }).message);
            toast({ title: "Couldn't save", description: (inner as { message: string }).message });
            return;
          }
        }
      }
      setFormError("Could not save preferences. Please try again.");
      toast({ title: "Couldn't save", description: "Try again in a moment." });
    },
  });

  if (query.isLoading) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Loading preferences…</p>;
  }
  if (query.isError) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive">Could not load preferences.</p>
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

  const tzOptions = buildTimezoneOptions(prefs.quiet_hours.tz);

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (mutation.isPending) return;
        mutation.mutate(prefs);
      }}
      className="space-y-8"
    >
      <div className="rounded-md border bg-card p-4">
        <h2 className="text-sm font-medium">Quick controls</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Mute every channel at once. Locked security emails are not affected.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPrefs((p) => muteAll(p, "push"))}
          >
            Mute all push
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPrefs((p) => muteAll(p, "email"))}
          >
            Mute all email
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPrefs((p) => muteAll(p, "in_app"))}
          >
            Mute all in-app
          </Button>
        </div>
      </div>

      {GROUPS.map((group) => (
        <section key={group.id} className="space-y-3">
          <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
            {group.label}
          </h3>
          <div className="space-y-2">
            {group.rows.map((row) => (
              <div
                key={row.key}
                className="rounded-md border p-3 sm:grid sm:grid-cols-[1fr_repeat(3,minmax(70px,auto))] sm:items-center sm:gap-4"
              >
                <div>
                  <p className="text-sm font-medium">{row.label}</p>
                  {row.hint ? <p className="text-xs text-muted-foreground">{row.hint}</p> : null}
                </div>
                {(["in_app", "email", "push"] as Channel[]).map((channel) => {
                  const meta = row.channels[channel];
                  const value = resolveChannel(prefs, channel, row);
                  return (
                    <div
                      key={channel}
                      className={cn(
                        "mt-2 flex items-center justify-between gap-2 sm:mt-0 sm:flex-col sm:items-center sm:justify-center"
                      )}
                    >
                      <span className="text-xs uppercase tracking-wide text-muted-foreground sm:order-1 sm:text-[10px]">
                        {channel.replace("_", "-")}
                      </span>
                      {meta.available ? (
                        <Switch
                          checked={value}
                          disabled={meta.locked}
                          aria-label={`${row.label} ${channel}`}
                          onCheckedChange={(checked) =>
                            setPrefs((current) => setChannel(current, channel, row, checked))
                          }
                        />
                      ) : (
                        <span aria-hidden="true" className="text-xs text-muted-foreground">
                          —
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </section>
      ))}

      <section className="space-y-3">
        <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Quiet hours
        </h3>
        <div className="space-y-3 rounded-md border p-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">Enable quiet hours</p>
              <p className="text-xs text-muted-foreground">
                Suppress push notifications during your set window. Email and digest are not
                affected.
              </p>
            </div>
            <Switch
              checked={prefs.quiet_hours.enabled}
              aria-label="Enable quiet hours"
              onCheckedChange={(checked) =>
                setPrefs((current) => ({
                  ...current,
                  quiet_hours: {
                    ...current.quiet_hours,
                    enabled: checked,
                    start: checked
                      ? (current.quiet_hours.start ?? "22:00")
                      : current.quiet_hours.start,
                    end: checked ? (current.quiet_hours.end ?? "08:00") : current.quiet_hours.end,
                  },
                }))
              }
            />
          </div>
          {prefs.quiet_hours.enabled ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label htmlFor="quiet-hours-from" className="flex flex-col gap-1 text-xs">
                <span className="font-medium text-muted-foreground">From</span>
                <Input
                  id="quiet-hours-from"
                  type="time"
                  value={prefs.quiet_hours.start ?? ""}
                  onChange={(event) =>
                    setPrefs((current) => ({
                      ...current,
                      quiet_hours: {
                        ...current.quiet_hours,
                        start: event.target.value || null,
                      },
                    }))
                  }
                />
              </label>
              <label htmlFor="quiet-hours-to" className="flex flex-col gap-1 text-xs">
                <span className="font-medium text-muted-foreground">To</span>
                <Input
                  id="quiet-hours-to"
                  type="time"
                  value={prefs.quiet_hours.end ?? ""}
                  onChange={(event) =>
                    setPrefs((current) => ({
                      ...current,
                      quiet_hours: {
                        ...current.quiet_hours,
                        end: event.target.value || null,
                      },
                    }))
                  }
                />
              </label>
              <label htmlFor="quiet-hours-tz" className="flex flex-col gap-1 text-xs">
                <span className="font-medium text-muted-foreground">Timezone</span>
                <select
                  id="quiet-hours-tz"
                  value={prefs.quiet_hours.tz}
                  onChange={(event) =>
                    setPrefs((current) => ({
                      ...current,
                      quiet_hours: { ...current.quiet_hours, tz: event.target.value },
                    }))
                  }
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                >
                  {tzOptions.map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ) : null}
        </div>
      </section>

      {formError ? (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
          {formError}
        </p>
      ) : null}

      <div className="flex justify-end">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : "Save preferences"}
        </Button>
      </div>
    </form>
  );
}
