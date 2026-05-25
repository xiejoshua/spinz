/**
 * Minimal testmail.app client for E2E inbox assertions.
 *
 * testmail.app provides a per-namespace catch-all inbox at
 * `{namespace}.{tag}@inbox.testmail.app`. The JSON REST endpoint at
 * `https://api.testmail.app/api/json` returns an `emails` array
 * (newest first) filtered by namespace + optional tag. Tests use the
 * timestamp suffix as the tag, so each run sees a fresh, isolated
 * slice of the inbox.
 *
 * See https://testmail.app/docs/#json. (An earlier version of this
 * helper used the GraphQL endpoint, but the schema there exposes a
 * singular `message` field — not the `messages` array we want — and
 * silently returned validation errors which the polling loop swallowed
 * as "still empty", causing every test to time out even when the email
 * had arrived. The JSON endpoint is simpler and matches the array
 * shape we expect.)
 *
 * Environment variables:
 * - `TESTMAIL_NAMESPACE` — operator-provisioned, e.g. `abcde`.
 * - `TESTMAIL_API_KEY` — operator-provisioned API key.
 *
 * Tests that depend on this helper must skip cleanly when either env
 * var is missing — see the spec files' `test.describe.skip(...)` gate.
 */

const ENDPOINT = "https://api.testmail.app/api/json";

export type TestmailMessage = {
  /** Subject line of the inbound email. */
  subject: string;
  /** Rendered HTML body (what Resend sent). */
  html: string;
  /** ISO timestamp of receipt at testmail.app. */
  timestamp: string;
};

type JsonInboxResponse = {
  result?: string;
  count?: number;
  emails?: Array<{
    subject?: string;
    html?: string | null;
    text?: string | null;
    timestamp?: number;
    timestamp_iso?: string;
    tag?: string;
  }>;
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
 * When a test signs up + verifies + then triggers a different email
 * (e.g. forgot-password) on the SAME inbox address, both emails land
 * under the same tag. The optional `subjectMatches` regex lets the
 * caller wait specifically for the email they want — otherwise a poll
 * for the second email would return the first one (already in the
 * inbox) on the very first fetch.
 */
export async function pollInbox({
  namespace,
  apiKey,
  tag,
  timeoutMs = 30_000,
  intervalMs = 2_000,
  subjectMatches,
}: {
  namespace: string;
  apiKey: string;
  tag: string;
  timeoutMs?: number;
  intervalMs?: number;
  subjectMatches?: RegExp;
}): Promise<TestmailMessage | null> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const result = await fetchInboxOnce({ namespace, apiKey, tag, subjectMatches });
    if (result !== null) return result;
    await delay(intervalMs);
  }
  return null;
}

async function fetchInboxOnce({
  namespace,
  apiKey,
  tag,
  subjectMatches,
}: {
  namespace: string;
  apiKey: string;
  tag: string;
  subjectMatches?: RegExp;
}): Promise<TestmailMessage | null> {
  // Query params per testmail.app docs: apikey, namespace, tag (optional
  // filter). The endpoint orders newest-first; we look at the most
  // recent matching message.
  const url = new URL(ENDPOINT);
  url.searchParams.set("apikey", apiKey);
  url.searchParams.set("namespace", namespace);
  if (tag) url.searchParams.set("tag", tag);
  // When filtering by subject we need the recent slice (newest first)
  // so the regex can find the email even if older ones for the same
  // tag are still in the inbox. Without a filter, limit=1 is fine.
  url.searchParams.set("limit", subjectMatches ? "10" : "1");

  const response = await fetch(url.toString(), { method: "GET" });
  if (!response.ok) {
    // Transient 5xx → let the polling loop retry; surface a null.
    return null;
  }
  const payload = (await response.json()) as JsonInboxResponse;
  const emails = payload.emails ?? [];
  if (emails.length === 0) return null;
  const candidate = subjectMatches
    ? emails.find((e) => subjectMatches.test(e.subject ?? ""))
    : emails[0];
  if (!candidate) return null;
  return {
    subject: candidate.subject ?? "",
    html: candidate.html ?? candidate.text ?? "",
    timestamp:
      candidate.timestamp_iso ??
      (typeof candidate.timestamp === "number" ? new Date(candidate.timestamp).toISOString() : ""),
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
