import { LogSheet } from "@/components/log-sheet";
import { BottomTabs } from "@/components/nav/bottom-tabs";
import { LogFab } from "@/components/nav/log-fab";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { PushBootstrap } from "@/components/notifications/push-bootstrap";
import { cookies } from "next/headers";
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
      <header className="sticky top-0 z-20 flex h-12 items-center justify-end gap-2 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/75">
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
