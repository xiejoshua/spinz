import { expect, test } from "@playwright/test";

/**
 * T084 — Wedge NFR validation (spec.md §6.1; TC-001; TC-E2E-003).
 *
 * The wedge interaction is the load-bearing screen of the MVP. CR-001
 * relaxed the original auto-prefill model — we now do Letterboxd-style
 * manual search → pick → rate → save. Spec target: p95 commit time
 * <8 seconds across 10 trials, including the manual search-pick step.
 *
 * This spec measures **opens → close** wall time from a fixed search
 * query against a backend that already has the album indexed. It needs
 * a live backend and a logged-in session, so it is opt-in via
 * `E2E_BACKEND_REACHABLE=true`. Outside CI we still register the spec
 * so `playwright test` lists it, but skip the bodies.
 *
 * The spec deliberately does NOT depend on the auth happy-path fixture
 * — it expects the runner to provide a valid `auxd_session` cookie via
 * `E2E_AUTH_COOKIE` (the same pattern documented in
 * `tests/e2e/auth.spec.ts`).
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";
const SEED_QUERY = process.env.E2E_WEDGE_QUERY ?? "carrie";
const SESSION_COOKIE = process.env.E2E_AUTH_COOKIE ?? "";

const TRIALS = 10;
const P95_BUDGET_MS = 8000;

test.describe("wedge NFR — commit time <8s p95", () => {
  test.skip(
    !BACKEND_REACHABLE,
    "Set E2E_BACKEND_REACHABLE=true with a live API + seeded album catalog to enable."
  );

  test("p95 of (open → search → pick → rate → save) is under 8s", async ({ page, context }) => {
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

    const durations: number[] = [];
    for (let trial = 0; trial < TRIALS; trial++) {
      await page.goto("/");
      // The FAB is always-mounted at (app)/layout level (T077/T078).
      const fab = page.getByRole("button", { name: /log/i }).first();
      await fab.waitFor();

      const started = Date.now();
      await fab.click();
      await page.getByRole("heading", { name: /log an album/i }).waitFor();

      await page.getByPlaceholder(/search/i).fill(SEED_QUERY);
      // First result becomes interactive once the debounced query lands
      // and renders. We pick the first option.
      const firstResult = page.getByRole("button", { name: /select/i }).first();
      await firstResult.click({ timeout: 5000 });

      // Set a 4-star rating via keyboard so we don't depend on hit-region
      // precision: the rating widget exposes the value via ARIA slider.
      const slider = page.getByRole("slider", { name: /rating/i });
      await slider.focus();
      for (let i = 0; i < 8; i++) {
        await slider.press("ArrowRight"); // half-star steps × 8 = 4.0
      }

      await page.getByRole("button", { name: /^log$/i }).click();
      await expect(page.getByText(/^logged|already logged|relisten/i).first()).toBeVisible({
        timeout: 5000,
      });
      const elapsed = Date.now() - started;
      durations.push(elapsed);

      // Reset state between trials.
      await page.reload();
    }

    durations.sort((a, b) => a - b);
    const p95Index = Math.ceil(durations.length * 0.95) - 1;
    const p95 = durations[p95Index];
    // eslint-disable-next-line no-console
    console.log(`wedge durations ms (sorted): ${durations.join(", ")} — p95=${p95}`);
    expect(p95).toBeLessThan(P95_BUDGET_MS);
  });
});
