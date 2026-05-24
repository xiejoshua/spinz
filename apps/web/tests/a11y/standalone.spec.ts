import { expect, test } from "@playwright/test";
import { auditRoute, setFakeSession } from "./helpers";

/**
 * T171 + REV-126 — A11y scans for top-level standalone routes.
 *
 * /legal/* and /suspended render outside the `(app)` shell so they
 * have unique a11y surfaces (banners, lawyer-placeholder asides,
 * suspended-account 403 messaging). The MVP gate is 0 CRITICAL
 * violations (see helpers.ts).
 *
 * REV-126 widens the original scan-only specs with explicit DOM checks
 * for the load-bearing landmarks on each surface:
 *   - /suspended: the appeal `mailto:` link (without it, suspended
 *     users have no way to contact us — a regulatory + UX issue);
 *   - /legal/privacy + /legal/terms: the lawyer-placeholder banner
 *     aside (without it, the placeholder text reads like a final policy).
 */
test.describe
  .parallel("a11y — standalone routes", () => {
    test("/legal/privacy passes WCAG 2.1 AA (0 critical) + has placeholder banner", async ({
      page,
    }) => {
      await auditRoute(page, "/legal/privacy");
      // REV-126 — confirm the lawyer-placeholder banner is on the page.
      // It's an <aside data-testid="placeholder-banner"> on both /legal/*
      // pages (see apps/web/src/app/legal/privacy/page.tsx).
      const banner = page.getByTestId("placeholder-banner");
      await expect(banner).toBeVisible();
      await expect(banner).toContainText(/placeholder/i);
    });

    test("/legal/terms passes WCAG 2.1 AA (0 critical) + has placeholder banner", async ({
      page,
    }) => {
      await auditRoute(page, "/legal/terms");
      const banner = page.getByTestId("placeholder-banner");
      await expect(banner).toBeVisible();
      await expect(banner).toContainText(/placeholder/i);
    });

    test("/suspended passes WCAG 2.1 AA (0 critical) + has appeal mailto", async ({
      context,
      page,
    }) => {
      // /suspended is reached when the API responds with the suspended
      // flag — for axe-core we just need to land on the page, so a
      // session cookie is enough (the page renders regardless of API).
      await page.goto("/");
      await setFakeSession(context);
      await auditRoute(page, "/suspended");
      // REV-126 — confirm the appeal `mailto:` link is present and
      // points to the documented appeals address (T159 contract). The
      // page contains both an inline anchor and a button — assert at
      // least one mailto link exists.
      const mailtoLinks = page.locator('a[href^="mailto:appeals@"]');
      await expect(mailtoLinks.first()).toBeVisible();
      await expect(mailtoLinks.first()).toHaveAttribute(
        "href",
        /^mailto:appeals@auxd\.xiejoshua\.com$/
      );
    });
  });
