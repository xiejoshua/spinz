"use client";

import { apiClient } from "@/lib/api-client";

// T141 — browser-side Web Push helpers.
//
// The prompt is gated by *user behaviour*, not first-session install,
// per the taxonomy doc:
//   "Permission prompt is not shown at first session — too aggressive.
//    Shown after the user's 3rd follow OR after 7 days of activity,
//    whichever comes first."
//
// We track both counters in localStorage. Both keys are namespaced under
// ``auxd:push:`` so a future schema bump can wipe the lot without
// disrupting other features.

const KEY_FIRST_VISIT_AT = "auxd:push:first_visit_at";
const KEY_FOLLOWS_COUNT = "auxd:push:follows_count";
const KEY_DISMISSED_AT = "auxd:push:dismissed_at";

export const PROMPT_FOLLOWS_THRESHOLD = 3;
export const PROMPT_AGE_THRESHOLD_MS = 7 * 24 * 60 * 60 * 1000;
export const PROMPT_DISMISS_COOLDOWN_MS = 14 * 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Browser capability detection
// ---------------------------------------------------------------------------

export function isPushSupported(): boolean {
  if (typeof window === "undefined") return false;
  if (typeof Notification === "undefined") return false;
  if (!("serviceWorker" in navigator)) return false;
  if (!("PushManager" in window)) return false;
  return true;
}

export function getCurrentPermission(): NotificationPermission | "unsupported" {
  if (!isPushSupported()) return "unsupported";
  return Notification.permission;
}

// ---------------------------------------------------------------------------
// Counters
// ---------------------------------------------------------------------------

function readNumber(key: string): number | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(key);
  if (raw === null) return null;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return null;
  return parsed;
}

function writeNumber(key: string, value: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, String(value));
}

export function markFirstVisit(now: number = Date.now()): void {
  if (typeof window === "undefined") return;
  if (window.localStorage.getItem(KEY_FIRST_VISIT_AT) !== null) return;
  writeNumber(KEY_FIRST_VISIT_AT, now);
}

export function readFirstVisitAt(): number | null {
  return readNumber(KEY_FIRST_VISIT_AT);
}

export function markFollow(): number {
  const current = readNumber(KEY_FOLLOWS_COUNT) ?? 0;
  const next = current + 1;
  writeNumber(KEY_FOLLOWS_COUNT, next);
  return next;
}

export function readFollowsCount(): number {
  return readNumber(KEY_FOLLOWS_COUNT) ?? 0;
}

export function markDismissed(now: number = Date.now()): void {
  writeNumber(KEY_DISMISSED_AT, now);
}

export function readDismissedAt(): number | null {
  return readNumber(KEY_DISMISSED_AT);
}

// ---------------------------------------------------------------------------
// Prompt criteria — pure function, unit-tested directly.
// ---------------------------------------------------------------------------

export type PromptCriteriaInput = {
  followsCount: number;
  firstVisitAt: number | null;
  dismissedAt: number | null;
  now: number;
};

export function shouldShowPushPrompt(input: PromptCriteriaInput): boolean {
  // Recently dismissed? Cool off for PROMPT_DISMISS_COOLDOWN_MS.
  if (input.dismissedAt !== null) {
    if (input.now - input.dismissedAt < PROMPT_DISMISS_COOLDOWN_MS) {
      return false;
    }
  }
  if (input.followsCount >= PROMPT_FOLLOWS_THRESHOLD) return true;
  if (input.firstVisitAt !== null) {
    if (input.now - input.firstVisitAt >= PROMPT_AGE_THRESHOLD_MS) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// VAPID public key — Base64URL → Uint8Array per Web Push spec.
// ---------------------------------------------------------------------------

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  if (typeof window === "undefined") {
    // Server-side path — defensive only; this function isn't called there.
    return new Uint8Array(0);
  }
  const rawData = window.atob(base64);
  const output = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    output[i] = rawData.charCodeAt(i);
  }
  return output;
}

// ---------------------------------------------------------------------------
// Subscription flow
// ---------------------------------------------------------------------------

async function registerServiceWorker(): Promise<ServiceWorkerRegistration> {
  // ``/sw.js`` is served from the public/ directory at the root scope so
  // the SW can handle pushes for the entire app.
  const existing = await navigator.serviceWorker.getRegistration("/sw.js");
  if (existing) return existing;
  return navigator.serviceWorker.register("/sw.js", { scope: "/" });
}

type SubscribeResult =
  | { ok: true; created: boolean; subscriptionId: string }
  | { ok: false; reason: "unsupported" | "denied" | "no_vapid_key" | "error"; error?: string };

export async function subscribeToPush(): Promise<SubscribeResult> {
  if (!isPushSupported()) {
    return { ok: false, reason: "unsupported" };
  }
  const vapidPublic = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
  if (!vapidPublic) {
    return { ok: false, reason: "no_vapid_key" };
  }
  let permission: NotificationPermission;
  try {
    permission = await Notification.requestPermission();
  } catch (err) {
    return { ok: false, reason: "error", error: String(err) };
  }
  if (permission !== "granted") {
    return { ok: false, reason: "denied" };
  }

  try {
    const reg = await registerServiceWorker();
    // If the user re-subscribes, return the existing subscription rather
    // than asking the push service for a fresh one — pushManager.subscribe
    // is idempotent server-side but the keys must match what the backend
    // last stored.
    let subscription = await reg.pushManager.getSubscription();
    if (subscription === null) {
      // Cast: PushManager.subscribe accepts BufferSource but the lib.dom.d.ts
      // narrows to ArrayBufferView<ArrayBuffer> — our Uint8Array is backed
      // by ArrayBufferLike which TS can't widen automatically. Cast through
      // the structural buffer type to satisfy the strict signature.
      const applicationServerKey = urlBase64ToUint8Array(vapidPublic).buffer as ArrayBuffer;
      subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey,
      });
    }
    const json = subscription.toJSON();
    const endpoint = json.endpoint ?? subscription.endpoint;
    const keys = json.keys ?? {};
    const p256dh = keys.p256dh;
    const auth = keys.auth;
    if (!endpoint || !p256dh || !auth) {
      return { ok: false, reason: "error", error: "incomplete subscription JSON" };
    }
    const response = await apiClient.post<{
      id: string;
      endpoint: string;
      created: boolean;
    }>("/api/v1/users/me/push-subscriptions", {
      endpoint,
      keys: { p256dh, auth },
    });
    return { ok: true, created: response.created, subscriptionId: response.id };
  } catch (err) {
    return { ok: false, reason: "error", error: String(err) };
  }
}

// Test-only reset of the localStorage counters. NOT exported via index;
// callers in unit tests can import this path directly.
export function _resetPushStateForTests(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY_FIRST_VISIT_AT);
  window.localStorage.removeItem(KEY_FOLLOWS_COUNT);
  window.localStorage.removeItem(KEY_DISMISSED_AT);
}
