import "server-only";

import { ServerApiError, serverApiGet } from "@/lib/api-server";
import { redirect } from "next/navigation";

/**
 * Resolve the current viewer's handle and redirect to the
 * corresponding /profile/{handle}/settings{suffix} canonical URL.
 *
 * Used by the legacy /settings/* routes during the merge into the
 * profile shell. If the session can't be resolved (401 or network)
 * the user is sent to /login.
 */
export async function redirectToProfileSettings(suffix = ""): Promise<never> {
  try {
    const me = await serverApiGet<{ handle: string }>("/api/v1/users/me");
    redirect(`/profile/${encodeURIComponent(me.handle)}/settings${suffix}`);
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }
}
