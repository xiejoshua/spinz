import { expect, test } from "@playwright/test";

/**
 * TC-E2E-003 — Log + rate + Aux + review an album in <25s.
 *
 * This is the load-bearing wedge interaction. NFR target is p95
 * <8s end-to-end (spec.md §6.1). The shorter wedge-only sample is
 * also covered by `log-wedge.spec.ts` (T084 perf guard). This spec
 * is the qualitative pass — does the journey succeed, does the
 * entry appear on the diary?
 *
 * Backend-reachable: requires a live API, a signed-in session, and
 * the MusicBrainz cache populated enough that "carrie" returns
 * results.
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";
const SESSION_COOKIE = process.env.E2E_AUTH_COOKIE ?? "";
const SEED_QUERY = process.env.E2E_WEDGE_QUERY ?? "carrie";

test.describe("TC-E2E-003: search → log → diary roundtrip", () => {
  test.skip(!BACKEND_REACHABLE, "Set E2E_BACKEND_REACHABLE=true with a live API to enable.");

  test("from home, search + log an album, see it appear on diary", async ({ page, context }) => {
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
    await page.goto("/");
    await page.getByRole("button", { name: /log/i }).first().click();

    await expect(page.getByRole("heading", { name: /log an album/i })).toBeVisible();
    await page.getByPlaceholder(/search/i).fill(SEED_QUERY);
    await page
      .getByRole("button", { name: /select/i })
      .first()
      .click({ timeout: 5000 });

    const slider = page.getByRole("slider", { name: /rating/i });
    await slider.focus();
    for (let i = 0; i < 8; i++) {
      await slider.press("ArrowRight"); // 4.0 stars
    }
    // Optional Aux toggle + short review text
    const auxToggle = page.getByRole("switch", { name: /aux/i });
    if (await auxToggle.isVisible()) {
      await auxToggle.click();
    }
    const reviewBox = page.getByLabel(/review|thoughts/i);
    if (await reviewBox.isVisible()) {
      await reviewBox.fill("E2E test review");
    }
    await page.getByRole("button", { name: /^log$/i }).click();
    await expect(page.getByText(/logged|already logged|relisten/i).first()).toBeVisible({
      timeout: 5000,
    });

    // Navigate to own profile → diary tab.
    await page.goto("/profile/me");
    await expect(page.getByText(SEED_QUERY, { exact: false }).first()).toBeVisible({
      timeout: 5000,
    });
  });
});
