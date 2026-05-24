"use client";

/**
 * REV-120 — root error boundary for any route segment under `/`.
 *
 * Next.js App Router calls this `error.tsx` whenever a Server or Client
 * Component throws inside a route segment. It wraps the segment in a
 * client-side React ErrorBoundary so the rest of the app keeps working.
 *
 * On mount we forward the error to Sentry via the shared
 * `lib/sentry.captureClientError` helper so production crashes show up
 * in the dashboards. UI follows the editorial design language —
 * mono-uppercase "ERROR" eyebrow, Newsreader display headline, hairline
 * separator, side-by-side primary/secondary buttons centered under it.
 *
 * Notes:
 * - Must be a client component (`"use client"`) per Next.js docs.
 * - The `digest` is a hash Next produces for production errors; we
 *   include it in the Sentry context so logs and stack traces can be
 *   correlated.
 * - "Back to home" links to `/`. For signed-in viewers the marketing
 *   landing redirects them to `/feed` server-side, so a single link
 *   works for both states.
 * - This boundary cannot catch errors thrown in the root layout itself
 *   — for that, see `global-error.tsx`.
 */

import { Button } from "@/components/ui/button";
import { captureClientError } from "@/lib/sentry";
import Link from "next/link";
import { useEffect } from "react";

type ErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function GlobalRouteError({ error, reset }: ErrorProps) {
  useEffect(() => {
    captureClientError(error, {
      digest: error.digest,
      location: typeof window !== "undefined" ? window.location.pathname : undefined,
      boundary: "app/error.tsx",
    });
  }, [error]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-6">
      <article className="w-full max-w-md space-y-7 text-center">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          Error
        </div>
        <h1
          className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
          style={{
            fontSize: "clamp(28px, 4.5vw, 40px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          Something went wrong.
        </h1>
        <div className="mx-auto h-px w-12" style={{ background: "var(--separator)" }} />
        <p className="font-sans text-[15px] leading-[1.55]" style={{ color: "var(--muted)" }}>
          We hit an unexpected error rendering this page. The team has been notified — try again,
          and head back to the home feed if it keeps happening.
        </p>
        {error.digest ? (
          <p
            className="font-mono"
            style={{
              fontSize: "11px",
              letterSpacing: "0.06em",
              color: "var(--muted)",
            }}
          >
            Reference: <code>{error.digest}</code>
          </p>
        ) : null}
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Button onClick={() => reset()}>Try again</Button>
          <Button asChild variant="outline">
            <Link href="/">Back to home</Link>
          </Button>
        </div>
      </article>
    </main>
  );
}
