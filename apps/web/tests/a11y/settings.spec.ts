import { test } from "@playwright/test";
import { auditRoute, setFakeSession } from "./helpers";

/**
 * T171 — A11y scans for `/settings/*` (the heaviest form surface).
 *
 * Forms + sub-navigation + privacy toggles + irreversible actions all
 * live here; this is where label/name/help-text/role wiring matters
 * most. Each panel gets its own scan because they render independent
 * RSC trees.
 */
test.describe
  .parallel("a11y — settings routes", () => {
    test.beforeEach(async ({ context, page }) => {
      await page.goto("/");
      await setFakeSession(context);
    });

    test("/settings (overview) passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/settings");
    });

    test("/settings/profile passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/settings/profile");
    });

    test("/settings/privacy passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/settings/privacy");
    });

    test("/settings/account passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/settings/account");
    });

    test("/settings/data passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/settings/data");
    });

    test("/settings/notifications passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/settings/notifications");
    });
  });
