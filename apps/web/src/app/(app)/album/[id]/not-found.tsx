/**
 * REV-123 — segment-specific 404 for `/album/[id]`.
 *
 * `page.tsx` calls `notFound()` when the backend returns 404 for an MBID
 * we don't have. Rendering this segment-scoped boundary keeps the (app)
 * shell (nav, header) around the empty state so the user can still
 * navigate.
 */

import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function AlbumNotFound() {
  return (
    <main className="flex min-h-[60dvh] flex-col items-center justify-center px-6">
      <div className="w-full max-w-md space-y-6 text-center">
        <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
          Album not found
        </p>
        <h1 className="text-2xl font-bold tracking-tight">We don't have that album</h1>
        <p className="text-sm text-muted-foreground">
          This album isn't in auxd yet — it may have been removed, or the link might be wrong. Try
          searching for it from the home feed.
        </p>
        <div className="flex flex-col gap-3">
          <Button asChild>
            <Link href="/search">Search for an album</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/">Back to home</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
