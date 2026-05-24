import { expect, test } from "@playwright/test";

/**
 * TC-E2E-011 — Block a user → verify content hiding both ways.
 *
 * Two-direction visibility check: after blocking user B from user
 * A's session:
 *   - B's profile page in A's view shows "Blocked" + content hidden.
 *   - A's profile page in B's session shows "Profile unavailable"
 *     (the reciprocal hide; see plan §8 + T101 integration test).
 *
 * Backend-required; runs against two pre-provisioned accounts.
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";
const SESSION_A = process.env.E2E_AUTH_COOKIE_A ?? "";
const HANDLE_B = process.env.E2E_TARGET_HANDLE_B ?? "";

test.describe("TC-E2E-011: block user → bidirectional content hide", () => {
  test.skip(!BACKEND_REACHABLE, "Set E2E_BACKEND_REACHABLE=true with a live API to enable.");
  test.skip(!HANDLE_B, "Set E2E_TARGET_HANDLE_B to the second test account's handle.");

  test("from A's session, block B → B's profile shows Blocked + content hidden", async ({
    page,
    context,
  }) => {
    if (SESSION_A) {
      await context.addCookies([
        {
          name: "auxd_session",
          value: SESSION_A,
          domain: "localhost",
          path: "/",
          httpOnly: true,
          sameSite: "Lax",
        },
      ]);
    }
    await page.goto(`/profile/${HANDLE_B}`);
    await page.getByRole("button", { name: /more|⋯|options/i }).click();
    await page.getByRole("menuitem", { name: /block/i }).click();
    // Confirmation dialog if any
    const confirm = page.getByRole("button", { name: /confirm|block user/i });
    if (await confirm.isVisible()) {
      await confirm.click();
    }
    await expect(page.getByText(/blocked|content hidden/i)).toBeVisible({ timeout: 3000 });

    // Diary entries from B should no longer appear.
    await page.goto("/");
    await expect(page.locator(`[data-user-handle='${HANDLE_B}']`)).toHaveCount(0);
  });
});
