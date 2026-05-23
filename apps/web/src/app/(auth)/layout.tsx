import Link from "next/link";
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b">
        <div className="container max-w-3xl py-4">
          <Link href="/" className="text-2xl font-bold tracking-tight">
            auxd
          </Link>
        </div>
      </header>
      <main className="container flex max-w-md flex-1 flex-col justify-center py-8">
        {children}
      </main>
      <footer className="border-t">
        <div className="container flex max-w-3xl items-center justify-end gap-4 py-4 text-xs text-muted-foreground">
          <Link href="/legal/privacy" className="hover:underline">
            Privacy
          </Link>
          <span aria-hidden="true">{"·"}</span>
          <Link href="/legal/terms" className="hover:underline">
            Terms
          </Link>
        </div>
      </footer>
    </div>
  );
}
