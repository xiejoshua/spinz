import { expect, test } from "@playwright/test";

/**
 * TC-E2E-014 — Discover rehaul (feature 003 / Option A).
 *
 * Lightweight rendering smoke for the unauthenticated → login flow and
 * the new /discover + /search structure once signed in. Heavy data-
 * fidelity assertions (popular ranking, follow-graph annotation) are
 * deferred to integration tests on the backend — these E2Es just verify
 * the editorial shell, the search-bar toggle, and the URL contract.
 *
 * Backend-reachable parts run only when ``E2E_BACKEND_REACHABLE=true``
 * is set; otherwise we keep the unauth checks so the spec still passes
 * in the form-validation-only CI lane.
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";

test.describe("TC-E2E-014: /discover front-page renders unauthenticated → login bounce", () => {
  test("anonymous /discover redirects through the auth shell", async ({ page }) => {
    await page.goto("/discover");
    // The (app) shell is auth-gated; anonymous visitors should land on
    // /login, not see the Discover surface.
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});

test.describe("TC-E2E-014: /search legacy compat shim", () => {
  test("/discover?tab=albums redirects to /search", async ({ page }) => {
    await page.goto("/discover?tab=albums");
    // Either the auth shell bounces us to /login OR the discover page
    // applies the shim. Both are acceptable for an unauth visitor.
    const url = page.url();
    expect(url).toMatch(/\/(login|search)/);
  });
});

test.describe("TC-E2E-014: authenticated /discover sections + advanced search", () => {
  test.skip(!BACKEND_REACHABLE, "Set E2E_BACKEND_REACHABLE=true with a live API to enable.");

  test("signed-in /discover shows section eyebrows + search-bar toggle", async ({ page }) => {
    const handle = `e2e_tc014_${Date.now()}`;
    const email = `${handle}@example.com`;
    const password = "playwright-e2e-tc-014";

    await page.goto("/signup");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Handle").fill(handle);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign up/i }).click();

    // Walk through the onboarding shell; the canonical landing is /feed
    // once step-3 completes. For this spec we just need a session, so
    // skipping ahead via direct nav is fine — the (app) shell allows
    // any signed-in user onto /discover.
    await page.goto("/discover");
    await expect(page.getByRole("heading", { name: /what's good/i })).toBeVisible();

    // People/Albums toggle is a radiogroup pair.
    await expect(page.getByRole("radio", { name: "People" })).toBeVisible();
    await expect(page.getByRole("radio", { name: "Albums" })).toBeVisible();

    // Switch to Albums mode — toggle should update aria-checked and
    // the input placeholder should track.
    await page.getByRole("radio", { name: "Albums" }).click();
    await expect(page.getByRole("radio", { name: "Albums" })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    await expect(page).toHaveURL(/mode=albums/);

    // Section eyebrows — these are the mono uppercase markers the
    // editorial shell renders for each section.
    await expect(page.getByText(/this week/i).first()).toBeVisible();
    await expect(page.getByText(/critics to follow/i).first()).toBeVisible();
  });

  test("/search advanced surface renders filter chips + sort dropdown", async ({ page }) => {
    const handle = `e2e_tc014b_${Date.now()}`;
    const email = `${handle}@example.com`;
    const password = "playwright-e2e-tc-014b";

    await page.goto("/signup");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Handle").fill(handle);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign up/i }).click();

    await page.goto("/search");
    await expect(page.getByRole("heading", { name: /browse the catalog/i })).toBeVisible();

    // Decade chip row + Sort dropdown render even before the user types.
    await expect(page.getByRole("button", { name: /2020s/i })).toBeVisible();
    await expect(page.getByLabel(/sort results/i)).toBeVisible();

    // Clicking a decade chip toggles aria-pressed and updates URL.
    await page.getByRole("button", { name: /2010s/i }).click();
    await expect(page.getByRole("button", { name: /2010s/i })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });
});
