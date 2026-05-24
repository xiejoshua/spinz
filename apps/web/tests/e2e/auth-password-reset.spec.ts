/**
 * E2E: forgot-password + reset-password happy path (002-auth-email-flows).
 *
 * Steps:
 * 1. Sign up at /signup with a testmail.app address; click the
 *    verification link so the user is `email_verified=true`
 *    (forgot-password silently no-ops for unverified accounts per
 *    FR-120, so the test must verify first).
 * 2. Log out.
 * 3. POST to /forgot-password with the email.
 * 4. Poll testmail.app for the reset email, parse `/reset-password/{token}`.
 * 5. Navigate, submit the new password.
 * 6. Confirm landing on /feed; verify old password fails + new succeeds.
 *
 * Gated behind `E2E_BACKEND_REACHABLE` + `TESTMAIL_NAMESPACE` +
 * `TESTMAIL_API_KEY` — skips cleanly otherwise.
 */

import { expect, test } from "@playwright/test";

import { extractTokenUrl, pollInbox, testmailAddress } from "./_testmail";

const BACKEND_REACHABLE = process.env.E2E_BACKEND_REACHABLE === "true";
const NAMESPACE = process.env.TESTMAIL_NAMESPACE ?? "";
const API_KEY = process.env.TESTMAIL_API_KEY ?? "";
const ENABLED = BACKEND_REACHABLE && Boolean(NAMESPACE) && Boolean(API_KEY);

test.describe("auth — forgot-password + reset-password happy path", () => {
  test.skip(
    !ENABLED,
    "Set E2E_BACKEND_REACHABLE=true plus TESTMAIL_NAMESPACE + TESTMAIL_API_KEY to enable."
  );

  test("signup → verify → forgot → click reset link → new password works", async ({
    page,
    context,
  }) => {
    const verifyTag = `reset-verify-${Date.now()}`;
    const resetTag = `reset-${Date.now()}`;
    const email = testmailAddress({ namespace: NAMESPACE, tag: verifyTag });
    const handle = `e2e_r${Date.now().toString().slice(-9)}`;
    const oldPassword = "playwright-old-pw-1";
    const newPassword = "playwright-new-pw-2";

    // 1. Sign up.
    await page.goto("/signup");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Handle").fill(handle);
    await page.getByLabel("Password").fill(oldPassword);
    await page.getByRole("button", { name: /sign up/i }).click();

    // 2. Pull the verification link out of testmail.app + click it.
    const verifyMessage = await pollInbox({
      namespace: NAMESPACE,
      apiKey: API_KEY,
      tag: verifyTag,
      timeoutMs: 60_000,
    });
    expect(verifyMessage, "verification email did not arrive").not.toBeNull();
    const verifyLink = extractTokenUrl(verifyMessage?.html ?? "", "/verify-email");
    expect(verifyLink, "verify-email link missing from HTML").not.toBeNull();
    if (!verifyLink) throw new Error("unreachable");
    await page.goto(`/verify-email/${verifyLink.token}`);
    await expect(page.getByRole("heading", { name: /email verified/i })).toBeVisible({
      timeout: 15_000,
    });

    // 3. Clear cookies to model the "logged out" state.
    await context.clearCookies();

    // 4. Request a reset.
    await page.goto("/forgot-password");
    // The form needs the same email; testmail.app catches everything
    // sent to `{namespace}.*@inbox.testmail.app`, but we use the
    // ORIGINAL signup address since the reset is keyed on User.email.
    await page.getByLabel("Email").fill(email);
    await page.getByRole("button", { name: /send reset link/i }).click();
    await expect(page.getByRole("heading", { name: /sent a reset link/i })).toBeVisible();

    // 5. Poll testmail.app for the reset email. testmail.app inboxes
    // are scoped per-tag — the reset email lands under the same
    // signup tag (the To: header is the same address). Use the
    // verify tag to filter and find the most recent message.
    const resetMessage = await pollInbox({
      namespace: NAMESPACE,
      apiKey: API_KEY,
      tag: verifyTag,
      timeoutMs: 60_000,
    });
    // The most-recent message in this tag is the reset (newer than
    // the verification message); fail loudly if the reset HTML's
    // /reset-password/{token} URL isn't there.
    expect(resetMessage, "reset email did not arrive").not.toBeNull();
    expect(resetMessage?.subject).toMatch(/reset your auxd password/i);
    const resetLink = extractTokenUrl(resetMessage?.html ?? "", "/reset-password");
    expect(resetLink, "reset link missing from HTML").not.toBeNull();
    if (!resetLink) throw new Error("unreachable");

    // 6. Click the link + set a new password.
    await page.goto(`/reset-password/${resetLink.token}`);
    await page.getByLabel("New password", { exact: true }).fill(newPassword);
    await page.getByLabel("Confirm new password").fill(newPassword);
    await page.getByRole("button", { name: /reset password/i }).click();
    await expect(page).toHaveURL(/\/feed$/);

    // 7. Old password no longer works.
    await context.clearCookies();
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(oldPassword);
    await page.getByRole("button", { name: /log in/i }).click();
    await expect(page.getByText(/wrong email or password/i)).toBeVisible();

    // 8. New password DOES work.
    await page.getByLabel("Password").fill(newPassword);
    await page.getByRole("button", { name: /log in/i }).click();
    // Lands somewhere inside the (app) shell — /feed for verified users.
    await expect(page).toHaveURL(/\/feed$/);
    // Silence ts-prune lint about unused locals.
    expect(resetTag.length).toBeGreaterThan(0);
  });
});
