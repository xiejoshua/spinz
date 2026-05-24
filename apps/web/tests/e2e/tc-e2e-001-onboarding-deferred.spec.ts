import { test } from "@playwright/test";

/**
 * TC-E2E-001 — DEFERRED-TO-V2 (CR-001).
 *
 * Original spec text (spec.md §10 table row 1): "Original: full
 * onboarding with streaming-platform connected." With CR-001
 * dropping the streaming-platform integration at MVP, the
 * streaming-connected variant of onboarding has no implementation
 * to test. The canonical MVP onboarding journey is exercised by
 * `tc-e2e-002-onboarding-mvp.spec.ts`.
 *
 * This file exists so the test ID is discoverable in the Playwright
 * test list and the launch checklist can confirm "TC-E2E-001
 * present" without operator confusion.
 */

test.describe("TC-E2E-001 — DEFERRED-TO-V2 (CR-001 streaming-onboarding path)", () => {
  test.skip("deferred per CR-001; see spec.md §10 row 1", async () => {
    // No-op. v2 plan inherits this test ID when streaming-platform
    // integration ships.
  });
});
