import AxeBuilder from "@axe-core/playwright";
import { type BrowserContext, type Page, expect } from "@playwright/test";

/**
 * T171 — WCAG 2.1 AA automated audit helpers.
 *
 * Every visible route in {@link apps/web/src/app} gets a sibling spec
 * that boots a Page, lets it settle, and runs the axe-core analyzer
 * scoped to WCAG 2.0/2.1 A + AA rules. The MVP gate is **0 CRITICAL
 * violations** — SERIOUS/MODERATE are reported but not enforced (see
 * `docs/a11y-audit.md` for the rationale + follow-up tracking).
 *
 * Authenticated routes lean on a non-validated session cookie. The
 * `(app)/layout.tsx` only checks for the *presence* of `auxd_session`,
 * not its integrity (validation happens inside React Server Components
 * that fetch the API and will throw 401 — those errors don't block
 * axe-core from analysing the shell + boundary errors). For surfaces
 * that don't render meaningful content without backend data the spec
 * sets `await page.waitForLoadState('domcontentloaded')` only.
 */

export const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] as const;

const SESSION_COOKIE = "auxd_session";

/**
 * Set a fake session cookie. Only the *presence* of `auxd_session`
 * gates entry through the `(app)/layout.tsx` redirect. Backend calls
 * will 401 — that's fine, the axe-core scan still gets the shell.
 */
export async function setFakeSession(context: BrowserContext): Promise<void> {
  const url = new URL(context.pages()[0]?.url() ?? "http://localhost:3000/");
  await context.addCookies([
    {
      name: SESSION_COOKIE,
      value: "a11y-fake-not-validated",
      domain: url.hostname,
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
}

export interface AxeRunOptions {
  /** Tags to filter rules against. Defaults to wcag2 a/aa + wcag21 a/aa. */
  tags?: readonly string[];
  /** Selector to scope axe-core to. Defaults to scanning the whole document. */
  include?: string;
  /** Selectors to exclude (e.g. third-party iframes). */
  exclude?: readonly string[];
}

export async function runAxeOnPage(
  page: Page,
  options: AxeRunOptions = {}
): Promise<{ critical: number; serious: number; moderate: number; minor: number }> {
  let builder = new AxeBuilder({ page }).withTags([...(options.tags ?? AXE_TAGS)]);
  if (options.include) {
    builder = builder.include(options.include);
  }
  for (const sel of options.exclude ?? []) {
    builder = builder.exclude(sel);
  }
  const results = await builder.analyze();
  const byImpact = {
    critical: 0,
    serious: 0,
    moderate: 0,
    minor: 0,
  };
  for (const v of results.violations) {
    if (v.impact && v.impact in byImpact) {
      byImpact[v.impact as keyof typeof byImpact] += 1;
    }
  }
  // Hard gate at MVP: 0 CRITICAL. Anything CRITICAL is a launch blocker
  // (e.g. missing form labels, contrast failures on submit buttons,
  // ARIA misuse that locks out screen readers).
  const criticalDetails = results.violations
    .filter((v) => v.impact === "critical")
    .map((v) => {
      const nodeSnippets = v.nodes
        .slice(0, 3)
        .map(
          (n) => `\n      target=${JSON.stringify(n.target)} html=${n.html?.slice(0, 200) ?? ""}`
        )
        .join("");
      return `${v.id} — ${v.description} (${v.nodes.length} node${v.nodes.length === 1 ? "" : "s"})${nodeSnippets}`;
    })
    .join("\n  ");
  expect(byImpact.critical, `critical a11y violations:\n  ${criticalDetails}`).toBe(0);
  return byImpact;
}

/**
 * Visit a route, soft-tolerate any HTTP errors that come from missing
 * backend data, run the axe analyzer. Returns the impact breakdown so
 * the caller can log totals.
 */
export async function auditRoute(
  page: Page,
  url: string,
  options: AxeRunOptions = {}
): Promise<{ critical: number; serious: number; moderate: number; minor: number }> {
  // We don't want a network 500 from a missing backend to crash the
  // navigation — domcontentloaded is enough to land in the React tree.
  await page.goto(url, { waitUntil: "domcontentloaded" });
  // Best-effort settle: many surfaces hydrate after RSC streaming,
  // but Playwright considers domcontentloaded fired immediately.
  await page.waitForTimeout(200);
  return runAxeOnPage(page, options);
}
