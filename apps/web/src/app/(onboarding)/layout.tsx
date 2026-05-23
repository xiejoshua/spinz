import { OnboardingProgress } from "@/components/nav/onboarding-progress";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

const SESSION_COOKIE = "auxd_session";

export default async function OnboardingLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  if (!cookieStore.get(SESSION_COOKIE)) {
    redirect("/login");
  }
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b">
        <div className="container max-w-3xl py-4">
          <h1 className="text-2xl font-bold tracking-tight">auxd</h1>
        </div>
        <OnboardingProgress />
      </header>
      <main className="container flex max-w-md flex-1 flex-col py-8">{children}</main>
    </div>
  );
}
