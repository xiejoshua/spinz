/**
 * E2E: forgot-password no-enumeration guard (002-auth-email-flows / FR-141).
 *
 * Submitting an unregistered email to /forgot-password must return the
 * same generic success copy AS A registered email — and crucially must
 * NOT send a real reset email. We poll testmail.app for a short window
 * after the request and assert the inbox stays empty.
 *
 * Gated behind `E2E_BACKEND_REACHABLE` + `TESTMAIL_NAMESPACE` +
 * `TESTMAIL_API_KEY` — skips cleanly otherwise.
 */

import { expect, test } from "@playwright/test";

import { pollInbox, testmailAddress } from "./_testmail";

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";
const NAMESPACE = process.env.TESTMAIL_NAMESPACE ?? "";
const API_KEY = process.env.TESTMAIL_API_KEY ?? "";
const ENABLED = BACKEND_REACHABLE && Boolean(NAMESPACE) && Boolean(API_KEY);

test.describe("auth — forgot-password no enumeration", () => {
  test.skip(
    !ENABLED,
    "Set E2E_BACKEND_REACHABLE=true plus TESTMAIL_NAMESPACE + TESTMAIL_API_KEY to enable."
  );

  test("unregistered email yields generic success + no inbound email", async ({ page }) => {
    const tag = `nonexistent-${Date.now()}`;
    const email = testmailAddress({ namespace: NAMESPACE, tag });

    // 1. Submit the form with an email that was never registered.
    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill(email);
    await page.getByRole("button", { name: /send reset link/i }).click();

    // 2. The generic success message must be visible regardless.
    await expect(page.getByRole("heading", { name: /sent a reset link/i })).toBeVisible();

    // 3. Poll testmail.app for a short window. No email should arrive.
    //    A short poll is intentional — the goal is to prove emptiness,
    //    not to verify Resend's full delivery latency. 8s is enough to
    //    catch any synchronous-ish miss; the real assertion is the
    //    structural one (forgot-password backend path returned without
    //    writing a token row).
    const arrived = await pollInbox({
      namespace: NAMESPACE,
      apiKey: API_KEY,
      tag,
      timeoutMs: 8_000,
      intervalMs: 2_000,
    });
    expect(arrived, "unexpected email arrived for unregistered address").toBeNull();
  });
});
