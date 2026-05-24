import { VerifyEmailClient } from "./verify-email-client";

/**
 * Email verification confirmation page.
 *
 * The (auth) layout already redirects already-logged-in users to /feed
 * BEFORE this page renders — but a user who clicks the verification
 * link from a different device may not have a session at all. That's
 * fine: ``POST /api/v1/auth/verify-email`` is anonymous-callable and
 * the route group's chrome (wordmark + footer) reads identically for
 * signed-out users.
 *
 * The single token segment comes in from the dynamic [token] folder
 * and is passed straight to the client component which performs the
 * one-shot verification POST on mount.
 */
export default async function VerifyEmailPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <VerifyEmailClient token={token} />;
}
