import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN ?? "";
const SENTRY_ENV =
  process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? process.env.NODE_ENV ?? "development";

export async function register() {
  if (!SENTRY_DSN) return;

  if (process.env.NEXT_RUNTIME === "nodejs") {
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: SENTRY_ENV,
      tracesSampleRate: 0,
      sendDefaultPii: false,
    });
  }

  if (process.env.NEXT_RUNTIME === "edge") {
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: SENTRY_ENV,
      tracesSampleRate: 0,
      sendDefaultPii: false,
    });
  }
}

export const onRequestError = Sentry.captureRequestError;
