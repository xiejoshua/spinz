/**
 * E2E: verify-email happy path (002-auth-email-flows).
 *
 * Signs up at /signup using a testmail.app inbox address, polls the
 * inbox for the verification email, parses the `/verify-email/{token}`
 * link out of the rendered HTML, navigates it, and asserts that the
 * resulting user payload reports `email_verified: true`.
 *
 * Gated behind THREE env vars — all must be present:
 * - `E2E_BACKEND_REACHABLE=true`  (the existing live-API gate)
 * - `TESTMAIL_NAMESPACE`           (operator-provisioned)
 * - `TESTMAIL_API_KEY`             (operator-provisioned)
 *
 * CI without testmail credentials skips cleanly via the
 * `test.describe.skip(...)` predicate below.
 */

import { expect, test } from "@playwright/test";

import { extractTokenUrl, pollInbox, testmailAddress } from "./_testmail";

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";
const NAMESPACE = process.env.TESTMAIL_NAMESPACE ?? "";
const API_KEY = process.env.TESTMAIL_API_KEY ?? "";
const ENABLED = BACKEND_REACHABLE && Boolean(NAMESPACE) && Boolean(API_KEY);

test.describe("auth — verify-email happy path", () => {
  test.skip(
    !ENABLED,
    "Set E2E_BACKEND_REACHABLE=true plus TESTMAIL_NAMESPACE + TESTMAIL_API_KEY to enable."
  );

  test("signup → testmail.app email arrives → click link → email_verified=true", async ({
    page,
    request,
  }) => {
    // Unique tag per run so concurrent tests don't share an inbox.
    const tag = `verify-${Date.now()}`;
    const email = testmailAddress({ namespace: NAMESPACE, tag });
    const handle = `e2e_v${Date.now().toString().slice(-9)}`;
    const password = "playwright-e2e-test-pw-1";

    // 1. Sign up.
    await page.goto("/signup");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Handle").fill(handle);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign up/i }).click();

    // Signup completes and the user lands somewhere inside the (app)
    // surface (onboarding → /onboarding/step-1, or /feed after first
    // pass). The exact landing is not the assertion — the email is.

    // 2. Poll testmail.app for the verification email.
    const message = await pollInbox({
      namespace: NAMESPACE,
      apiKey: API_KEY,
      tag,
      timeoutMs: 60_000,
    });
    expect(message, "verification email did not arrive within 60s").not.toBeNull();
    expect(message?.subject).toMatch(/confirm your email/i);

    // 3. Pull /verify-email/{token} out of the HTML body.
    const parsed = extractTokenUrl(message?.html ?? "", "/verify-email");
    expect(parsed, "verify-email link not found in email HTML").not.toBeNull();
    if (!parsed) throw new Error("unreachable");

    // 4. Navigate the link. The page POSTs the token to the API on mount.
    await page.goto(`/verify-email/${parsed.token}`);
    await expect(page.getByRole("heading", { name: /email verified/i })).toBeVisible({
      timeout: 15_000,
    });

    // 5. Confirm via the API that `email_verified` flipped.
    const meResponse = await request.get("/api/v1/users/me");
    expect(meResponse.ok()).toBe(true);
    const me = await meResponse.json();
    expect(me.email).toBe(email);
    expect(me.email_verified).toBe(true);
  });
});
