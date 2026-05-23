"use client";

import { capture } from "@/lib/posthog";

const ONBOARDING_START_TS_KEY = "auxd:onboarding:started_at";
const ONBOARDING_FOLLOWS_STASH_KEY = "auxd:onboarding:follows_summary";

export type OnboardingFollowsSummary = {
  follows_count: number;
  critic_seed_kept_pct: number;
};

/**
 * Stash the result of the follow-critics step so the success page can
 * include it in the `onboarding.completed` event without re-querying the
 * backend. localStorage is intentional: the success page is a separate
 * route, so React state can't span the navigation.
 */
export function stashOnboardingFollows(summary: OnboardingFollowsSummary): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ONBOARDING_FOLLOWS_STASH_KEY, JSON.stringify(summary));
}

function readOnboardingFollowsStash(): OnboardingFollowsSummary | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(ONBOARDING_FOLLOWS_STASH_KEY);
  if (raw === null) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<OnboardingFollowsSummary>;
    if (typeof parsed.follows_count !== "number") return null;
    if (typeof parsed.critic_seed_kept_pct !== "number") return null;
    return {
      follows_count: parsed.follows_count,
      critic_seed_kept_pct: parsed.critic_seed_kept_pct,
    };
  } catch {
    return null;
  }
}

/**
 * Record the start of an onboarding session so `emitOnboardingCompleted`
 * can compute `time_to_complete_ms`. Call once on the first onboarding
 * step the user lands on; subsequent calls are idempotent (the existing
 * timestamp survives).
 */
export function markOnboardingStart(): void {
  if (typeof window === "undefined") return;
  if (window.localStorage.getItem(ONBOARDING_START_TS_KEY) !== null) return;
  window.localStorage.setItem(ONBOARDING_START_TS_KEY, String(Date.now()));
}

/**
 * Fire the `onboarding.completed` PostHog event with the success metrics
 * defined in product-spec/success-metrics. Reads `follows_count` and
 * `critic_seed_kept_pct` from the stash that step-2 wrote; falls back
 * to zeros when the stash is missing (deep-link / cleared storage), so
 * the event still fires and the funnel shows the user reached the end.
 *
 * `top5_rated_count` is fixed at 0 — T079 (rate-a-few-albums) is not in
 * the MVP onboarding flow per CR-001.
 */
export function emitOnboardingCompleted(): void {
  if (typeof window === "undefined") return;
  const stash = readOnboardingFollowsStash();
  const properties: Record<string, unknown> = {
    follows_count: stash?.follows_count ?? 0,
    critic_seed_kept_pct: stash?.critic_seed_kept_pct ?? 0,
    top5_rated_count: 0,
  };
  const startedAtRaw = window.localStorage.getItem(ONBOARDING_START_TS_KEY);
  if (startedAtRaw !== null) {
    const startedAt = Number(startedAtRaw);
    if (Number.isFinite(startedAt) && startedAt > 0) {
      properties.time_to_complete_ms = Date.now() - startedAt;
    }
  }
  capture("onboarding.completed", properties);
  window.localStorage.removeItem(ONBOARDING_START_TS_KEY);
  window.localStorage.removeItem(ONBOARDING_FOLLOWS_STASH_KEY);
}
