import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Minimal layout for the legal/* placeholder pages (T161).
 *
 * Standalone — no (auth) or (app) layout, no session cookie check.
 * The pages are reachable from the public footer on /login + /signup
 * (T038) so anonymous prospective users can read them before signing
 * up.
 */
export default function LegalLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b">
        <div className="container flex max-w-3xl items-center justify-between py-4">
          <Link href="/" className="text-2xl font-bold tracking-tight">
            auxd
          </Link>
          <nav className="text-sm">
            <Link href="/" className="text-muted-foreground hover:text-foreground hover:underline">
              Back to app
            </Link>
          </nav>
        </div>
      </header>
      <main className="container flex max-w-3xl flex-1 flex-col gap-6 py-10">{children}</main>
      <footer className="border-t">
        <div className="container flex max-w-3xl items-center justify-between py-4 text-xs text-muted-foreground">
          <span>(c) auxd</span>
          <nav className="flex gap-4">
            <Link href="/legal/privacy" className="hover:underline">
              Privacy
            </Link>
            <Link href="/legal/terms" className="hover:underline">
              Terms
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
