/**
 * REV-123 — segment-specific 404 for `/review/[id]`.
 *
 * `page.tsx` calls `notFound()` for both 404 (review deleted) and 403
 * (review hidden because the author blocked you / set visibility to
 * followers). The copy is intentionally generic so it doesn't leak
 * which case fired.
 */

import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function ReviewNotFound() {
  return (
    <main className="flex min-h-[60dvh] flex-col items-center justify-center px-6">
      <div className="w-full max-w-md space-y-6 text-center">
        <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Review not available
        </p>
        <h1 className="text-2xl font-bold tracking-tight">Can't show this review</h1>
        <p className="text-sm text-muted-foreground">
          The review you tried to view doesn't exist or isn't visible to you. It may have been
          deleted, or the author may have changed their visibility settings.
        </p>
        <div className="flex flex-col gap-3">
          <Button asChild>
            <Link href="/">Back to home</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
