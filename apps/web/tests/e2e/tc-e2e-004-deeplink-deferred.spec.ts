import { test } from "@playwright/test";

/**
 * TC-E2E-004 — DEFERRED-TO-V2 (CR-001).
 *
 * Original spec text (spec.md §10): "Original: discover album via
 * social feed → streaming-platform deep-link." Streaming-platform
 * deep-link integration is deferred to v2. MVP album detail pages
 * link to MusicBrainz / Discogs canonical URLs only — no per-user
 * streaming context.
 */

test.describe("TC-E2E-004 — DEFERRED-TO-V2 (CR-001 streaming-deeplink)", () => {
  test.skip("deferred per CR-001; see spec.md §10 row 4", async () => {
    // No-op.
  });
});
