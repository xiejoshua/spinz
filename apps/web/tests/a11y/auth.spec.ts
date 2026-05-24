import { test } from "@playwright/test";
import { auditRoute } from "./helpers";

/**
 * T171 — A11y scans for unauthenticated entry points.
 *
 * These routes render fully without a session cookie, so they're the
 * easiest to scan — no fake-auth needed.
 */
test.describe
  .parallel("a11y — auth routes", () => {
    test("/login passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/login");
    });

    test("/signup passes WCAG 2.1 AA (0 critical)", async ({ page }) => {
      await auditRoute(page, "/signup");
    });
  });
