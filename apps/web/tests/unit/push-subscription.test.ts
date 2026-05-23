import {
  PROMPT_AGE_THRESHOLD_MS,
  PROMPT_DISMISS_COOLDOWN_MS,
  PROMPT_FOLLOWS_THRESHOLD,
  shouldShowPushPrompt,
} from "@/lib/push-subscription";
import { describe, expect, it } from "vitest";

const NOW = new Date("2026-05-23T12:00:00Z").getTime();

describe("shouldShowPushPrompt", () => {
  it("returns false when below both thresholds", () => {
    expect(
      shouldShowPushPrompt({
        followsCount: 0,
        firstVisitAt: NOW - 1000,
        dismissedAt: null,
        now: NOW,
      })
    ).toBe(false);
  });

  it("returns true when followsCount >= threshold", () => {
    expect(
      shouldShowPushPrompt({
        followsCount: PROMPT_FOLLOWS_THRESHOLD,
        firstVisitAt: NOW - 1000,
        dismissedAt: null,
        now: NOW,
      })
    ).toBe(true);
  });

  it("returns true when activity age >= threshold even with zero follows", () => {
    expect(
      shouldShowPushPrompt({
        followsCount: 0,
        firstVisitAt: NOW - PROMPT_AGE_THRESHOLD_MS,
        dismissedAt: null,
        now: NOW,
      })
    ).toBe(true);
  });

  it("returns false when activity age below threshold and follows below threshold", () => {
    expect(
      shouldShowPushPrompt({
        followsCount: PROMPT_FOLLOWS_THRESHOLD - 1,
        firstVisitAt: NOW - PROMPT_AGE_THRESHOLD_MS + 1000,
        dismissedAt: null,
        now: NOW,
      })
    ).toBe(false);
  });

  it("suppresses prompt for the cooldown window after dismiss", () => {
    expect(
      shouldShowPushPrompt({
        followsCount: PROMPT_FOLLOWS_THRESHOLD,
        firstVisitAt: NOW - PROMPT_AGE_THRESHOLD_MS,
        dismissedAt: NOW - 1000,
        now: NOW,
      })
    ).toBe(false);
  });

  it("re-enables prompt after cooldown window elapses", () => {
    expect(
      shouldShowPushPrompt({
        followsCount: PROMPT_FOLLOWS_THRESHOLD,
        firstVisitAt: NOW - PROMPT_AGE_THRESHOLD_MS,
        dismissedAt: NOW - PROMPT_DISMISS_COOLDOWN_MS - 1000,
        now: NOW,
      })
    ).toBe(true);
  });

  it("handles null firstVisitAt without crashing", () => {
    expect(
      shouldShowPushPrompt({
        followsCount: 0,
        firstVisitAt: null,
        dismissedAt: null,
        now: NOW,
      })
    ).toBe(false);
  });

  it("follows threshold beats age threshold (either is sufficient)", () => {
    expect(
      shouldShowPushPrompt({
        followsCount: PROMPT_FOLLOWS_THRESHOLD,
        firstVisitAt: null,
        dismissedAt: null,
        now: NOW,
      })
    ).toBe(true);
  });
});
