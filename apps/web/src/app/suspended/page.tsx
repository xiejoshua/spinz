"use client";

import { Button } from "@/components/ui/button";
import { ApiError, apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import { useAuthStore } from "@/stores/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/**
 * Public route shown to users whose account has been suspended (T159).
 *
 * Reachable both by direct navigation (the api-client redirects here on
 * any 403 with ``error: "account_suspended"``) and by /suspended deep
 * links from the appeal email. Standalone — no (app) layout, since the
 * user is locked out of the authenticated shell.
 */
export default function SuspendedPage() {
  const router = useRouter();
  const clearUser = useAuthStore((s) => s.clear);

  useEffect(() => {
    capture("account.suspended_page_viewed");
  }, []);

  const onLogout = async () => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch (error) {
      if (!(error instanceof ApiError)) {
        // Network error — still clear local state.
      }
    }
    clearUser();
    router.push("/login");
  };

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-6">
      <div className="w-full max-w-md space-y-6 text-center">
        <h1 className="text-3xl font-bold tracking-tight">Account suspended</h1>
        <p className="text-sm text-muted-foreground">
          Your account is currently suspended pending review. You can't log activity, follow other
          users, or interact with content until the suspension is lifted.
        </p>
        <p className="text-sm text-muted-foreground">
          If you think this is a mistake, email us at{" "}
          <a
            href="mailto:appeals@auxd.xiejoshua.com"
            className="font-medium text-foreground hover:underline"
          >
            appeals@auxd.xiejoshua.com
          </a>
          .
        </p>
        <div className="flex flex-col gap-3">
          <Button asChild>
            <a href="mailto:appeals@auxd.xiejoshua.com">Email appeal</a>
          </Button>
          <Button variant="outline" onClick={() => void onLogout()}>
            Log out
          </Button>
        </div>
      </div>
    </div>
  );
}
