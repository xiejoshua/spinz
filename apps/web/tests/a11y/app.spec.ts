import { test } from "@playwright/test";
import { auditRoute, setFakeSession } from "./helpers";

/**
 * T171 — A11y scans for `(app)` group routes (post-auth surface).
 *
 * The session cookie bypasses `(app)/layout.tsx` redirect. Backend
 * fetches in RSC layers will 401 — that's fine, the React shell still
 * renders the navigation, error boundaries, and skeleton states for
 * axe-core to inspect.
 */
test.describe
  .parallel("a11y — app routes", () => {
    test.beforeEach(async ({ context, page }) => {
      await page.goto("/");
      await setFakeSession(context);
    });

    test("/ (home feed) passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/");
    });

    test("/search passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/search");
    });

    test("/up-next passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/up-next");
    });

    test("/discover passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/discover");
    });

    test("/notifications passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/notifications");
    });

    test("/album/[id] passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/album/test-album");
    });

    test("/review/[id] passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/review/test-review");
    });

    test("/profile/[handle] passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/profile/test_handle");
    });

    test("/profile/[handle]/reviews passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/profile/test_handle/reviews");
    });
  });
