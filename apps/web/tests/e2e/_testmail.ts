/**
 * Minimal testmail.app GraphQL client for E2E inbox assertions.
 *
 * testmail.app provides a per-namespace catch-all inbox at
 * `{namespace}.{tag}@inbox.testmail.app`. Their GraphQL endpoint returns
 * any messages received within the supplied namespace, optionally
 * filtered by tag. Tests use the timestamp suffix as the tag, so each
 * run sees a fresh, isolated inbox.
 *
 * See https://testmail.app/docs for the full schema. This wrapper
 * exposes one helper — {@link pollInbox} — which polls until either a
 * message arrives or the timeout expires.
 *
 * Environment variables:
 * - `TESTMAIL_NAMESPACE` — operator-provisioned, e.g. `abcde`.
 * - `TESTMAIL_API_KEY` — operator-provisioned bearer key.
 *
 * Tests that depend on this helper must skip cleanly when either env
 * var is missing — see the spec files' `test.describe.skip(...)` gate.
 */

const ENDPOINT = "https://api.testmail.app/api/graphql";

export type TestmailMessage = {
  /** Subject line of the inbound email. */
  subject: string;
  /** Rendered HTML body (what Resend sent). */
  html: string;
  /** ISO timestamp of receipt at testmail.app. */
  timestamp: string;
};

type GraphqlInboxResponse = {
  data?: {
    inbox?: {
      count: number;
      result: string;
      messages?: Array<{
        subject: string;
        html: string | null;
        text: string | null;
        timestamp: string | number;
      }>;
    };
  };
  errors?: Array<{ message: string }>;
};

export function testmailAddress({
  namespace,
  tag,
}: {
  namespace: string;
  tag: string;
}): string {
  // testmail.app inbound addresses always follow this shape — the tag
  // can be any URL-safe string and gets parsed back out server-side.
  return `${namespace}.${tag}@inbox.testmail.app`;
}

/**
 * Poll testmail.app for the first message matching the supplied
 * namespace + tag. Returns the message on arrival or `null` on
 * timeout. Default poll cadence: 2s.
 *
 * The `livequery` shape returns a Promise that resolves as soon as a
 * message arrives, but we use the simple polling form for portability
 * — it matches the testmail.app docs' beginner example and keeps the
 * dependency surface small.
 */
export async function pollInbox({
  namespace,
  apiKey,
  tag,
  timeoutMs = 30_000,
  intervalMs = 2_000,
}: {
  namespace: string;
  apiKey: string;
  tag: string;
  timeoutMs?: number;
  intervalMs?: number;
}): Promise<TestmailMessage | null> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const result = await fetchInboxOnce({ namespace, apiKey, tag });
    if (result !== null) return result;
    await delay(intervalMs);
  }
  return null;
}

async function fetchInboxOnce({
  namespace,
  apiKey,
  tag,
}: {
  namespace: string;
  apiKey: string;
  tag: string;
}): Promise<TestmailMessage | null> {
  const query = `
    query Inbox($namespace: String!, $tag: String, $limit: Int) {
      inbox(namespace: $namespace, tag: $tag, limit: $limit) {
        count
        result
        messages {
          subject
          html
          text
          timestamp
        }
      }
    }
  `;
  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      query,
      variables: { namespace, tag, limit: 1 },
    }),
  });
  if (!response.ok) {
    // Don't bail — give the timeout loop a chance to recover from a
    // transient 5xx. Return null so the caller treats this poll as
    // "still empty".
    return null;
  }
  const payload = (await response.json()) as GraphqlInboxResponse;
  if (payload.errors && payload.errors.length > 0) {
    // Same — surface a null and let the polling loop retry.
    return null;
  }
  const messages = payload.data?.inbox?.messages ?? [];
  if (messages.length === 0) return null;
  const first = messages[0];
  return {
    subject: first.subject ?? "",
    html: first.html ?? first.text ?? "",
    timestamp:
      typeof first.timestamp === "number"
        ? new Date(first.timestamp).toISOString()
        : (first.timestamp ?? ""),
  };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Parse a {prefix}/{token} URL out of HTML email content. Used to
 * extract the verify-email or reset-password link out of the
 * received email body without committing to a single template shape.
 */
export function extractTokenUrl(
  html: string,
  prefix: "/verify-email" | "/reset-password"
): { token: string; url: string } | null {
  // The template emits an absolute URL — match `{origin}{prefix}/{token}`
  // and grab the trailing token segment up to the next whitespace,
  // quote, or HTML attribute boundary.
  const escapedPrefix = prefix.replace(/[/]/g, "\\/");
  const re = new RegExp(`(https?:\\/\\/[^\\s"'<>]+${escapedPrefix}\\/([A-Za-z0-9\\-_]+))`, "i");
  const match = re.exec(html);
  if (!match) return null;
  return { url: match[1], token: match[2] };
}
