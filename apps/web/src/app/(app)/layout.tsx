import { LogSheet } from "@/components/log-sheet";
import { BottomTabs } from "@/components/nav/bottom-tabs";
import { LogFab } from "@/components/nav/log-fab";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { PushBootstrap } from "@/components/notifications/push-bootstrap";
import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

const SESSION_COOKIE = "auxd_session";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  if (!cookieStore.get(SESSION_COOKIE)) {
    redirect("/login");
  }
  return (
    <div className="flex min-h-dvh flex-col pb-16">
      <header
        className="sticky top-0 z-20 flex h-14 items-center justify-between px-6 backdrop-blur-md"
        style={{
          background: "color-mix(in oklab, var(--background) 80%, transparent)",
          borderBottom: "1px solid var(--separator)",
        }}
      >
        <Link
          href="/"
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
      <BottomTabs />
      <PushBootstrap />
    </div>
  );
}
