"use client";

/**
 * REV-120 — last-resort error boundary for the root layout itself.
 *
 * `error.tsx` cannot catch errors thrown inside `app/layout.tsx`. This
 * `global-error.tsx` is Next.js's escape hatch: it *replaces* the root
 * layout when it triggers, which is why it must render its own `<html>`
 * and `<body>` tags.
 *
 * Kept intentionally minimal — no Providers, no Toaster, no Tailwind
 * preflight (since this fires before/around the root layout). Inline
 * styles only. The goal is a readable error page even when the rest of
 * the app's chrome is broken.
 */

import { captureClientError } from "@/lib/sentry";
import { useEffect } from "react";

type GlobalErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    captureClientError(error, {
      digest: error.digest,
      boundary: "app/global-error.tsx",
    });
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          fontFamily:
            "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
          margin: 0,
          minHeight: "100dvh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "1.5rem",
          background: "#fafafa",
          color: "#111",
        }}
      >
        <main style={{ maxWidth: "28rem", textAlign: "center" }}>
          <h1 style={{ fontSize: "1.875rem", fontWeight: 700, margin: "0 0 1rem" }}>
            Something went wrong
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#555", margin: "0 0 1.5rem" }}>
            auxd hit an unexpected error and couldn't render. The team has been notified.
          </p>
          {error.digest ? (
            <p
              style={{
                fontSize: "0.75rem",
                color: "#888",
                margin: "0 0 1.5rem",
                fontFamily: "monospace",
              }}
            >
              Reference: {error.digest}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() => reset()}
            style={{
              padding: "0.5rem 1.25rem",
              fontSize: "0.875rem",
              fontWeight: 500,
              background: "#111",
              color: "#fff",
              border: 0,
              borderRadius: "0.375rem",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
