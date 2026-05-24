import { expect, test } from "@playwright/test";

/**
 * TC-E2E-002 — Full MVP onboarding (signup → handle → follow ≥3
 * critics → critic-seed feed). Per CR-001, TC-E2E-002 is the
 * **canonical MVP onboarding flow** (TC-E2E-001's streaming path is
 * deferred).
 *
 * Backend-reachable: requires a live API + critic-seed roster
 * (T117) provisioned. Without `E2E_BACKEND_REACHABLE=true`, the
 * test is skipped — the form-validation portion is already covered
 * by `auth.spec.ts`.
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";

test.describe("TC-E2E-002: full MVP onboarding (canonical CR-001 path)", () => {
  test.skip(!BACKEND_REACHABLE, "Set E2E_BACKEND_REACHABLE=true with a live API to enable.");

  test("signup → step-1 → step-2 → step-3 lands on feed with ≥5 critic-seed entries", async ({
    page,
  }) => {
    const handle = `e2e_tc002_${Date.now()}`;
    const email = `${handle}@example.com`;
    const password = "playwright-e2e-tc-002";

    await page.goto("/signup");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Handle").fill(handle);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign up/i }).click();

    // Step 1: welcome + display name (or whatever copy is set)
    await expect(page).toHaveURL(/\/onboarding\/step-1$/);
    await page.getByRole("button", { name: /next|continue/i }).click();

    // Step 2: follow ≥3 critics from the seed roster.
    await expect(page).toHaveURL(/\/onboarding\/step-2$/);
    // The follow cards are rendered server-side from CriticSeed
    // roster (T117). Click the first three.
    const followBtns = page.getByRole("button", { name: /follow/i });
    await followBtns.nth(0).click();
    await followBtns.nth(1).click();
    await followBtns.nth(2).click();
    await page.getByRole("button", { name: /next|continue/i }).click();

    // Step 3: notification-perms invite (optional).
    await expect(page).toHaveURL(/\/onboarding\/step-3$/);
    await page.getByRole("button", { name: /finish|done|continue/i }).click();

    // Land on feed; should have ≥5 critic-seed entries visible.
    await expect(page).toHaveURL(/\/$/);
    const entries = page.locator("[data-testid='feed-entry']");
    await expect(entries.nth(4)).toBeVisible({ timeout: 5000 });
  });
});
