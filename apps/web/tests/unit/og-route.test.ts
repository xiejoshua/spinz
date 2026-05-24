import { describe, expect, it } from "vitest";

import { ALBUM_TITLE_MAX, REVIEW_EXCERPT_MAX, backendUrl, truncate } from "@/app/api/og/helpers";

describe("truncate", () => {
  it("passes empty strings through unchanged", () => {
    expect(truncate("", 100)).toBe("");
  });

  it("returns the input verbatim when within the budget", () => {
    expect(truncate("short", 100)).toBe("short");
  });

  it("clips to maxLength and appends a single ellipsis", () => {
    const longString = "x".repeat(REVIEW_EXCERPT_MAX + 50);
    const out = truncate(longString, REVIEW_EXCERPT_MAX);
    expect(out.length).toBe(REVIEW_EXCERPT_MAX + 1); // +1 for the ellipsis char
    expect(out.endsWith("…")).toBe(true);
  });

  it("strips trailing whitespace before the ellipsis", () => {
    // Pad with spaces so the slice lands on whitespace at the boundary.
    const input = `${"a".repeat(20)}   ${"b".repeat(80)}`;
    const out = truncate(input, 23);
    expect(out).not.toMatch(/\s…$/);
    expect(out.endsWith("…")).toBe(true);
  });
});

describe("backendUrl", () => {
  it("uses API_BACKEND_URL when set", () => {
    const prev = process.env.API_BACKEND_URL;
    try {
      process.env.API_BACKEND_URL = "https://api.auxd.example.com";
      expect(backendUrl("/api/v1/albums/abc")).toBe(
        "https://api.auxd.example.com/api/v1/albums/abc"
      );
    } finally {
      if (prev === undefined) {
        // biome-ignore lint/performance/noDelete: must actually unset the env var (assigning undefined coerces to "undefined" string).
        delete process.env.API_BACKEND_URL;
      } else {
        process.env.API_BACKEND_URL = prev;
      }
    }
  });

  it("falls back to localhost:8000 when env var is unset", () => {
    const prev = process.env.API_BACKEND_URL;
    try {
      // biome-ignore lint/performance/noDelete: must actually unset the env var.
      delete process.env.API_BACKEND_URL;
      const result = backendUrl("/api/v1/reviews/x");
      expect(result.startsWith("http://localhost:8000")).toBe(true);
      expect(result.endsWith("/api/v1/reviews/x")).toBe(true);
    } finally {
      if (prev === undefined) {
        // biome-ignore lint/performance/noDelete: must actually unset the env var (assigning undefined coerces to "undefined" string).
        delete process.env.API_BACKEND_URL;
      } else {
        process.env.API_BACKEND_URL = prev;
      }
    }
  });
});

describe("OG sizing constants", () => {
  it("ALBUM_TITLE_MAX is sane", () => {
    expect(ALBUM_TITLE_MAX).toBeGreaterThan(20);
    expect(ALBUM_TITLE_MAX).toBeLessThanOrEqual(200);
  });

  it("REVIEW_EXCERPT_MAX is the contracted 200 chars", () => {
    expect(REVIEW_EXCERPT_MAX).toBe(200);
  });
});
