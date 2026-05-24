import { test } from "@playwright/test";
import { auditRoute, setFakeSession } from "./helpers";

/**
 * T171 — A11y scans for top-level standalone routes.
 *
 * /legal/* and /suspended render outside the `(app)` shell so they
 * have unique a11y surfaces (banners, lawyer-placeholder asides,
 * suspended-account 403 messaging).
 */
test.describe
  .parallel("a11y — standalone routes", () => {
    test("/legal/privacy passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/legal/privacy");
    });

    test("/legal/terms passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/legal/terms");
    });

    test("/suspended passes WCAG 2.1 AA (0 critical)", async ({ context, page }) => {
      // /suspended is reached when the API responds with the suspended
      // flag — for axe-core we just need to land on the page, so a
      // session cookie is enough (the page renders regardless of API).
      await page.goto("/");
      await setFakeSession(context);
      await auditRoute(page, "/suspended");
    });
  });
