import { OnboardingProgress } from "@/components/nav/onboarding-progress";
import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

const SESSION_COOKIE = "auxd_session";

export default async function OnboardingLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  if (!cookieStore.get(SESSION_COOKIE)) {
    redirect("/login");
  }
  return (
    <div
      className="flex min-h-dvh flex-col"
      style={{ background: "var(--surface)" }}
    >
      <header className="px-6 pt-8 pb-6">
        <Link
          href="/"
          className="inline-block font-serif text-[24px] font-semibold leading-none tracking-[-0.015em]"
          style={{ color: "var(--foreground)", fontFamily: "var(--font-serif)" }}
        >
          auxd
        </Link>
        <OnboardingProgress />
      </header>
      <main className="flex flex-1 items-start justify-center px-6 pb-16">
        <div className="w-full max-w-[480px]">{children}</div>
      </main>
    </div>
  );
}
