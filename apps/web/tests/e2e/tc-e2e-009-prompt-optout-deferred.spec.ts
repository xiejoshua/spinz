import { test } from "@playwright/test";

/**
 * TC-E2E-009 — DEFERRED-TO-V2 (CR-001).
 *
 * Original spec text (spec.md §10): "Original: Settings → disable
 * auto-prompts → verify no prompts." Tied to TC-E2E-008's just-
 * finished prompt cluster; no auto-prompt surface at MVP. The
 * settings panel for notification preferences (TC-E2E-010) covers
 * the orthogonal "in-app notification opt-outs" path.
 */

test.describe("TC-E2E-009 — DEFERRED-TO-V2 (CR-001 prompt opt-out)", () => {
  test.skip("deferred per CR-001; see spec.md §10 row 9", async () => {
    // No-op.
  });
});
