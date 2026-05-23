"use client";

import posthog from "posthog-js";

const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY ?? "";
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://us.i.posthog.com";

let initialized = false;

export function initPostHogBrowser(): void {
  if (typeof window === "undefined") return;
  if (initialized) return;
  if (!POSTHOG_KEY) return;
  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    capture_pageview: "history_change",
    capture_pageleave: true,
    autocapture: false,
    persistence: "localStorage+cookie",
  });
  initialized = true;
}

export function capture(event: string, properties?: Record<string, unknown>): void {
  if (!initialized) return;
  posthog.capture(event, properties);
}

export function identify(distinctId: string, properties?: Record<string, unknown>): void {
  if (!initialized) return;
  posthog.identify(distinctId, properties);
}

export function reset(): void {
  if (!initialized) return;
  posthog.reset();
}

export { posthog };
