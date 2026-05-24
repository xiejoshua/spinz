import { expect, test } from "@playwright/test";

/**
 * TC-E2E-006 — Sort reviews by Most Liked.
 *
 * Album detail page exposes a "Most Liked" / "Most Recent" toggle
 * that re-orders the review list and persists across reload via
 * query string or user preference.
 *
 * Backend-required: needs ≥2 reviews on the test album with
 * differing like counts so the sort can be visually verified.
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";
const SESSION_COOKIE = process.env.E2E_AUTH_COOKIE ?? "";
const ALBUM_ID = process.env.E2E_TEST_ALBUM_ID ?? "";

test.describe("TC-E2E-006: sort reviews by Most Liked persists", () => {
  test.skip(!BACKEND_REACHABLE, "Set E2E_BACKEND_REACHABLE=true with a live API to enable.");
  test.skip(!ALBUM_ID, "Set E2E_TEST_ALBUM_ID=<album-id> with seeded reviews to enable.");

  test("toggle Most Liked → order changes → reload preserves selection", async ({
    page,
    context,
  }) => {
    if (SESSION_COOKIE) {
      await context.addCookies([
        {
          name: "auxd_session",
          value: SESSION_COOKIE,
          domain: "localhost",
          path: "/",
          httpOnly: true,
          sameSite: "Lax",
        },
      ]);
    }
    await page.goto(`/album/${ALBUM_ID}`);
    const beforeFirstReview = await page
      .locator("[data-testid='review-card']")
      .first()
      .textContent();

    await page.getByRole("button", { name: /most liked/i }).click();
    await expect(page.locator("[data-testid='review-card']").first()).not.toHaveText(
      beforeFirstReview ?? ""
    );

    const afterFirstReview = await page
      .locator("[data-testid='review-card']")
      .first()
      .textContent();
    await page.reload();
    await expect(page.locator("[data-testid='review-card']").first()).toHaveText(
      afterFirstReview ?? ""
    );
  });
});
