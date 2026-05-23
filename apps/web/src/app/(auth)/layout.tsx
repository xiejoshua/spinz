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
    </div>
  );
}
