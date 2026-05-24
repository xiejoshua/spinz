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
 * in the dashboards. The UI is a friendly fallback with a "Try again"
 * button (calls `reset()` — Next re-renders the segment) and a "Back to
 * home" link.
 *
 * Notes:
 * - Must be a client component (`"use client"`) per Next.js docs.
 * - The `digest` is a hash Next produces for production errors; we
 *   include it in the Sentry context so logs and stack traces can be
 *   correlated.
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
      <div className="w-full max-w-md space-y-6 text-center">
        <h1 className="text-3xl font-bold tracking-tight">Something went wrong</h1>
        <p className="text-sm text-muted-foreground">
          We hit an unexpected error rendering this page. The team has been notified — please try
          again, and head back to the home feed if it keeps happening.
        </p>
        {error.digest ? (
          <p className="text-xs text-muted-foreground">
            Reference: <code className="font-mono">{error.digest}</code>
          </p>
        ) : null}
        <div className="flex flex-col gap-3">
          <Button onClick={() => reset()}>Try again</Button>
          <Button asChild variant="outline">
            <Link href="/">Back to home</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
