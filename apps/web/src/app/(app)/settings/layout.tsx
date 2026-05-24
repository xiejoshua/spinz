import type { ReactNode } from "react";

/**
 * Legacy /settings/* layout. Every child page redirects server-side
 * to /profile/{handle}/settings/{section} via redirectToProfileSettings,
 * so this layout never actually renders user-facing chrome — kept as
 * a passthrough so the route segment doesn't error.
 */
export default function SettingsLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
