import { test } from "@playwright/test";

/**
 * TC-E2E-008 — DEFERRED-TO-V2 (CR-001).
 *
 * Original spec text (spec.md §10): "Original: just-finished prompt
 * appears + log from prompt." The JustFinishedPrompt cluster
 * depends on streaming-platform listening-history (T123-T130 plan
 * cluster) which is deferred to v2 per CR-001. No active surface
 * at MVP.
 */

test.describe("TC-E2E-008 — DEFERRED-TO-V2 (CR-001 just-finished prompt)", () => {
  test.skip("deferred per CR-001; see spec.md §10 row 8", async () => {
    // No-op.
  });
});
