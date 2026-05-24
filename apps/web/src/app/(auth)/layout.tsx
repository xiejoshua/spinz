import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Editorial auth shell — full-bleed --paper, centered narrow form,
 * Newsreader wordmark, hairline footer. Mirrors the landing's chrome
 * register so /login and /signup read as the same product.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className="flex min-h-dvh flex-col"
      style={{ background: "var(--surface)" }}
    >
      <header className="px-6 pt-8">
        <Link
          href="/"
          className="inline-block font-serif text-[24px] font-semibold leading-none tracking-[-0.015em]"
          style={{ color: "var(--foreground)", fontFamily: "var(--font-serif)" }}
        >
          auxd
        </Link>
      </header>
      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-[400px]">{children}</div>
      </main>
      <footer className="px-6 pb-8">
        <div
          className="flex items-center justify-center gap-4 font-sans text-xs"
          style={{ color: "var(--muted)" }}
        >
          <Link href="/legal/privacy" className="hover:underline">
            Privacy
          </Link>
          <span aria-hidden="true">·</span>
          <Link href="/legal/terms" className="hover:underline">
            Terms
          </Link>
        </div>
      </footer>
    </div>
  );
}
