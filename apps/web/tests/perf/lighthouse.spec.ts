import { chromium, test } from "@playwright/test";
import { playAudit } from "playwright-lighthouse";

/**
 * T172 — Frontend Lighthouse perf audit (spec.md §6.1).
 *
 * Lighthouse runs against four critical screens:
 *   - `/` (home feed) — p95<500ms target
 *   - `/album/[id]`   — p95<400ms target
 *   - `/up-next`      — backlog UI (mobile-heavy)
 *   - `/notifications` — bell + dropdown interaction surface
 *
 * Thresholds:
 *   - Performance:    ≥80 (lower than the 90+ best-in-class because
 *                     auxd is a data-heavy social app, not a
 *                     marketing page)
 *   - Accessibility:  ≥90 (axe-core's automated pass surfaces in
 *                     Lighthouse too)
 *   - Best Practices: ≥90
 *   - SEO:            n/a (gated routes; not measured)
 *
 * Runs behind `E2E_BACKEND_REACHABLE=true` because without backend
 * data the pages just show skeletons, which trivially pass perf
 * scoring and don't reflect real-world numbers.
 */

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";

const THRESHOLDS = {
  performance: 80,
  accessibility: 90,
  "best-practices": 90,
};

// Use a fixed remote-debug port so playwright-lighthouse can attach.
const LH_PORT = 9222;

test.describe
  .serial("perf — Lighthouse (backend-required)", () => {
    test.skip(
      !BACKEND_REACHABLE,
      "Set E2E_BACKEND_REACHABLE=true with a live API + signed-in session to enable."
    );

    // Lighthouse drives its own Chromium with CDP; the Playwright fixture
    // would conflict, so we use Playwright only as a launcher + cookie
    // injector and hand off to playwright-lighthouse for the audit.
    test("home feed scores ≥80 perf / ≥90 a11y / ≥90 best-practices", async () => {
      const browser = await chromium.launch({ args: [`--remote-debugging-port=${LH_PORT}`] });
      try {
        await playAudit({
          url: `${process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000"}/`,
          thresholds: THRESHOLDS,
          port: LH_PORT,
        });
      } finally {
        await browser.close();
      }
    });

    test("album detail scores ≥80 perf / ≥90 a11y / ≥90 best-practices", async () => {
      const browser = await chromium.launch({ args: [`--remote-debugging-port=${LH_PORT}`] });
      try {
        await playAudit({
          url: `${process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000"}/album/test-album`,
          thresholds: THRESHOLDS,
          port: LH_PORT,
        });
      } finally {
        await browser.close();
      }
    });

    test("up-next scores ≥80 perf / ≥90 a11y / ≥90 best-practices", async () => {
      const browser = await chromium.launch({ args: [`--remote-debugging-port=${LH_PORT}`] });
      try {
        await playAudit({
          url: `${process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000"}/up-next`,
          thresholds: THRESHOLDS,
          port: LH_PORT,
        });
      } finally {
        await browser.close();
      }
    });

    test("notifications scores ≥80 perf / ≥90 a11y / ≥90 best-practices", async () => {
      const browser = await chromium.launch({ args: [`--remote-debugging-port=${LH_PORT}`] });
      try {
        await playAudit({
          url: `${process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000"}/notifications`,
          thresholds: THRESHOLDS,
          port: LH_PORT,
        });
      } finally {
        await browser.close();
      }
    });
  });
