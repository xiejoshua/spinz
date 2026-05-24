/**
 * REV-120 — root 404 handler.
 *
 * Catches any route that doesn't match a segment, plus any explicit
 * `notFound()` call from a Server Component (see `(app)/album/[id]` and
 * `(app)/review/[id]` which use this when the backend returns 404).
 *
 * Plain Server Component — no need for client-side state. The styling
 * matches the suspended/legal standalone routes so the experience is
 * consistent.
 */

import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-6">
      <div className="w-full max-w-md space-y-6 text-center">
        <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">404</p>
        <h1 className="text-3xl font-bold tracking-tight">Couldn't find that</h1>
        <p className="text-sm text-muted-foreground">
          The page you tried to load doesn't exist (or might have been deleted by its owner). Check
          the URL, or head back to the home feed.
        </p>
        <Button asChild>
          <Link href="/">Back to home</Link>
        </Button>
      </div>
    </main>
  );
}
