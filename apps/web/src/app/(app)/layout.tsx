import { AuthHydrator } from "@/components/auth/auth-hydrator";
import { LogSheet } from "@/components/log-sheet";
import { BottomTabs } from "@/components/nav/bottom-tabs";
import { FloatingThemeToggle } from "@/components/nav/floating-theme-toggle";
import { LogFab } from "@/components/nav/log-fab";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { PushBootstrap } from "@/components/notifications/push-bootstrap";
import { ServerApiError, serverApiGet } from "@/lib/api-server";
import type { SanitizedUser } from "@/stores/auth";
import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

const SESSION_COOKIE = "auxd_session";

/** Try to load the current user; tolerate transient backend failures. */
async function loadViewer(): Promise<SanitizedUser | null> {
  try {
    return await serverApiGet<SanitizedUser>("/api/v1/users/me");
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      return null;
    }
    // 5xx, network blip — don't break navigation; the client store
    // can rehydrate from localStorage on the next render.
    return null;
  }
}

export default async function AppLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  if (!cookieStore.get(SESSION_COOKIE)) {
    redirect("/login");
  }
  const viewer = await loadViewer();
  return (
    <div className="flex min-h-dvh flex-col pb-16">
      <AuthHydrator user={viewer} />
      <header
        className="sticky top-0 z-20 flex h-14 items-center justify-between px-6 backdrop-blur-md"
        style={{
          background: "color-mix(in oklab, var(--background) 80%, transparent)",
          borderBottom: "1px solid var(--separator)",
        }}
      >
        <Link
          href="/feed"
          className="font-serif text-[22px] font-semibold leading-none tracking-[-0.015em]"
          style={{ color: "var(--foreground)", fontFamily: "var(--font-serif)" }}
        >
          auxd
        </Link>
        <NotificationBell />
      </header>
      <main className="flex-1">{children}</main>
      <LogFab />
      <LogSheet />
      <FloatingThemeToggle />
      <BottomTabs />
      <PushBootstrap />
    </div>
  );
}
