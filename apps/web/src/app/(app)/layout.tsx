import { LogSheet } from "@/components/log-sheet";
import { BottomTabs } from "@/components/nav/bottom-tabs";
import { LogFab } from "@/components/nav/log-fab";
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
      <main className="flex-1">{children}</main>
      <LogFab />
      <LogSheet />
      <BottomTabs />
    </div>
  );
}
