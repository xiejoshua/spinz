import { expect, test } from "@playwright/test";

/**
 * TC-E2E-007 — Add album to Up Next, later log it, verify auto-remove.
 *
 * Critical UX contract: when an album in the user's backlog is
 * logged via the wedge, it auto-removes from /up-next and a toast
 * confirms ("removed from Up Next"). Spec §4.6 + plan §8.
 *
 * Backend-required for the full loop; the in-memory parts run
 * against a logged-in dev session.
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";
const SESSION_COOKIE = process.env.E2E_AUTH_COOKIE ?? "";
const ALBUM_ID = process.env.E2E_BACKLOG_ALBUM_ID ?? "";

test.describe("TC-E2E-007: backlog → log → auto-remove + toast", () => {
  test.skip(!BACKEND_REACHABLE, "Set E2E_BACKEND_REACHABLE=true with a live API to enable.");
  test.skip(!ALBUM_ID, "Set E2E_BACKLOG_ALBUM_ID to an album NOT yet in backlog.");

  test("add to Up Next from album detail → log it → it's gone from /up-next", async ({
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
    // Add to backlog from album detail.
    await page.goto(`/album/${ALBUM_ID}`);
    await page.getByRole("button", { name: /add to up next|backlog/i }).click();
    await expect(page.getByText(/added/i)).toBeVisible({ timeout: 3000 });

    // Verify presence on /up-next.
    await page.goto("/up-next");
    await expect(page.locator(`[data-album-id="${ALBUM_ID}"]`)).toBeVisible();

    // Log it via the wedge (route via the FAB).
    await page.getByRole("button", { name: /log/i }).first().click();
    await page.getByPlaceholder(/search/i).fill(ALBUM_ID);
    await page
      .getByRole("button", { name: /select/i })
      .first()
      .click({ timeout: 5000 });
    await page.getByRole("button", { name: /^log$/i }).click();
    await expect(page.getByText(/removed from up next/i)).toBeVisible({ timeout: 5000 });

    // Reload /up-next; album is gone.
    await page.goto("/up-next");
    await expect(page.locator(`[data-album-id="${ALBUM_ID}"]`)).not.toBeVisible();
  });
});
