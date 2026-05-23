import * as Sentry from "@sentry/nextjs";

export function captureClientError(error: unknown, context?: Record<string, unknown>): void {
  Sentry.captureException(error, { extra: context });
}

export function captureClientMessage(
  message: string,
  level: Sentry.SeverityLevel = "info",
  context?: Record<string, unknown>
): void {
  Sentry.captureMessage(message, { level, extra: context });
}

export { Sentry };
