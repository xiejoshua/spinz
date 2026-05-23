import { ProfileReviewsList } from "@/components/profile-reviews/profile-reviews-list";
import type { Metadata } from "next";
import Link from "next/link";

type Params = Promise<{ handle: string }>;

/**
 * Reviews-only profile sub-route (T094).
 *
 * Surfaces the existing :func:`EditReviewDialog` and
 * :func:`DeleteReviewConfirmation` owner controls (T092) when the viewer
 * is the owner — the album-detail reviews list never shows them because
 * a stranger's album page is the wrong place to manage your own
 * reviews. This is.
 */
export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { handle } = await params;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  return {
    title: `Reviews by @${cleaned} — auxd`,
    description: `Reviews written by ${cleaned} on auxd`,
    openGraph: {
      title: `Reviews by @${cleaned} on auxd`,
      description: `Reviews written by ${cleaned} on auxd`,
    },
  };
}

export default async function ProfileReviewsPage({ params }: { params: Params }) {
  const { handle } = await params;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  return (
    <article className="container max-w-3xl space-y-6 py-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">@{cleaned}</h1>
        <p className="text-sm text-muted-foreground">
          Reviews ·{" "}
          <Link
            href={`/profile/${encodeURIComponent(cleaned)}`}
            className="underline-offset-2 hover:underline"
          >
            Back to diary
          </Link>
        </p>
      </header>
      <ProfileReviewsList handle={cleaned} />
    </article>
  );
}
