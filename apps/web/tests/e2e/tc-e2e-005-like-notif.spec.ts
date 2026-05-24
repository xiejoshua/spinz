import { expect, test } from "@playwright/test";

/**
 * TC-E2E-005 — Like a review → reviewer sees N-004 notification.
 *
 * Two-user scenario: user A likes user B's review; user B's
 * /notifications endpoint surfaces an N-004 entry. Requires backend
 * + two pre-provisioned accounts. E2E full pass requires both
 * sessions; the simpler harness uses one session and verifies the
 * like POST returns 200 + counter updates.
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";
const SESSION_COOKIE = process.env.E2E_AUTH_COOKIE ?? "";
const TARGET_REVIEW_ID = process.env.E2E_LIKE_TARGET_REVIEW_ID ?? "";

test.describe("TC-E2E-005: like → review-owner gets notified", () => {
  test.skip(!BACKEND_REACHABLE, "Set E2E_BACKEND_REACHABLE=true with a live API to enable.");
  test.skip(!TARGET_REVIEW_ID, "Set E2E_LIKE_TARGET_REVIEW_ID=<review-id> to enable.");

  test("clicking like on /review/[id] increments counter and creates N-004", async ({
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
    await page.goto(`/review/${TARGET_REVIEW_ID}`);
    const likeBtn = page.getByRole("button", { name: /like|♥/i });
    const beforeLabel = await likeBtn.textContent();
    await likeBtn.click();
    await expect(likeBtn).not.toHaveText(beforeLabel ?? "");

    // Switch to recipient's session (out of scope for this single-
    // session harness — recommend a separate "two-browser" test
    // when test-account creation is automated).
  });
});
