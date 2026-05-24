import { test } from "@playwright/test";
import { auditRoute, setFakeSession } from "./helpers";

/**
 * T171 — A11y scans for onboarding steps (signup → handle → critics).
 * Requires a session cookie to bypass `(onboarding)/layout.tsx` guard;
 * backend calls will 401 but the React shell still renders.
 */
test.describe
  .parallel("a11y — onboarding routes", () => {
    test.beforeEach(async ({ context, page }) => {
      await page.goto("/");
      await setFakeSession(context);
    });

    test("/onboarding/step-1 passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/onboarding/step-1");
    });

    test("/onboarding/step-2 passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/onboarding/step-2");
    });

    test("/onboarding/step-3 passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/onboarding/step-3");
    });
  });
