import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  emitOnboardingCompleted,
  markOnboardingStart,
  stashOnboardingFollows,
} from "@/lib/analytics";

const captureMock = vi.fn();

vi.mock("@/lib/posthog", () => ({
  capture: (event: string, props?: Record<string, unknown>) => {
    captureMock(event, props);
  },
}));

const ONBOARDING_START_TS_KEY = "auxd:onboarding:started_at";
const ONBOARDING_FOLLOWS_STASH_KEY = "auxd:onboarding:follows_summary";

class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length(): number {
    return this.store.size;
  }
  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }
  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
  removeItem(key: string): void {
    this.store.delete(key);
  }
  clear(): void {
    this.store.clear();
  }
}

beforeEach(() => {
  vi.stubGlobal("window", {
    localStorage: new MemoryStorage(),
  });
  captureMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("markOnboardingStart", () => {
  it("writes the current timestamp on first call", () => {
    const before = Date.now();
    markOnboardingStart();
    const stored = window.localStorage.getItem(ONBOARDING_START_TS_KEY);
    expect(stored).not.toBeNull();
    expect(Number(stored)).toBeGreaterThanOrEqual(before);
  });

  it("is idempotent: a second call leaves the original timestamp intact", () => {
    markOnboardingStart();
    const first = window.localStorage.getItem(ONBOARDING_START_TS_KEY);
    markOnboardingStart();
    expect(window.localStorage.getItem(ONBOARDING_START_TS_KEY)).toBe(first);
  });
});

describe("stashOnboardingFollows", () => {
  it("serialises the summary to localStorage", () => {
    stashOnboardingFollows({ follows_count: 5, critic_seed_kept_pct: 80 });
    expect(window.localStorage.getItem(ONBOARDING_FOLLOWS_STASH_KEY)).toBe(
      JSON.stringify({ follows_count: 5, critic_seed_kept_pct: 80 })
    );
  });

  it("overwrites any prior stash", () => {
    stashOnboardingFollows({ follows_count: 1, critic_seed_kept_pct: 50 });
    stashOnboardingFollows({ follows_count: 7, critic_seed_kept_pct: 100 });
    const parsed = JSON.parse(window.localStorage.getItem(ONBOARDING_FOLLOWS_STASH_KEY) as string);
    expect(parsed).toEqual({ follows_count: 7, critic_seed_kept_pct: 100 });
  });
});

describe("emitOnboardingCompleted", () => {
  it("fires `onboarding.completed` with stash + duration when both are present", () => {
    const fakeNow = 1_700_000_000_000;
    window.localStorage.setItem(ONBOARDING_START_TS_KEY, String(fakeNow - 12_345));
    stashOnboardingFollows({ follows_count: 4, critic_seed_kept_pct: 75 });

    vi.spyOn(Date, "now").mockReturnValue(fakeNow);
    emitOnboardingCompleted();

    expect(captureMock).toHaveBeenCalledTimes(1);
    const [event, props] = captureMock.mock.calls[0];
    expect(event).toBe("onboarding.completed");
    expect(props).toMatchObject({
      follows_count: 4,
      critic_seed_kept_pct: 75,
      top5_rated_count: 0,
      time_to_complete_ms: 12_345,
    });
  });

  it("falls back to zeros when no stash exists", () => {
    emitOnboardingCompleted();
    expect(captureMock).toHaveBeenCalledTimes(1);
    expect(captureMock.mock.calls[0][1]).toMatchObject({
      follows_count: 0,
      critic_seed_kept_pct: 0,
      top5_rated_count: 0,
    });
  });

  it("omits time_to_complete_ms when no start timestamp exists", () => {
    stashOnboardingFollows({ follows_count: 3, critic_seed_kept_pct: 100 });
    emitOnboardingCompleted();
    const [, props] = captureMock.mock.calls[0];
    expect(props).not.toHaveProperty("time_to_complete_ms");
  });

  it("clears the stash + start timestamp after firing", () => {
    window.localStorage.setItem(ONBOARDING_START_TS_KEY, "1234567");
    stashOnboardingFollows({ follows_count: 1, critic_seed_kept_pct: 100 });
    emitOnboardingCompleted();
    expect(window.localStorage.getItem(ONBOARDING_START_TS_KEY)).toBeNull();
    expect(window.localStorage.getItem(ONBOARDING_FOLLOWS_STASH_KEY)).toBeNull();
  });

  it("ignores a stash that is not valid JSON", () => {
    window.localStorage.setItem(ONBOARDING_FOLLOWS_STASH_KEY, "{not json");
    emitOnboardingCompleted();
    expect(captureMock.mock.calls[0][1]).toMatchObject({
      follows_count: 0,
      critic_seed_kept_pct: 0,
    });
  });
});
