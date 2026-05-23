import { ReviewReadingView } from "@/components/review-reading-view";
import type { AlbumDetailResponse, DiaryRow } from "@/lib/album-types";
import { ServerApiError, serverApiGet } from "@/lib/api-server";
import type { Review, ReviewUserCard } from "@/lib/review-types";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

type Params = Promise<{ id: string }>;

type SiteUrlOptions = {
  fallback?: string;
};

function getSiteUrl({ fallback = "http://localhost:3000" }: SiteUrlOptions = {}): string {
  return process.env.NEXT_PUBLIC_SITE_URL ?? fallback;
}

/**
 * Single-review payload used by both `loadReview` and `generateMetadata`.
 * The shape mirrors what the backend `_serialize_review` returns plus a
 * sidecar for the reviewer's user card and the parent album payload.
 */
type ReviewPagePayload = {
  review: Review;
  user: ReviewUserCard | undefined;
  album: AlbumDetailResponse["album"];
  viewer_entry: DiaryRow | null;
};

async function loadReview(reviewId: string): Promise<ReviewPagePayload | null> {
  try {
    return await serverApiGet<ReviewPagePayload>(`/api/v1/reviews/${encodeURIComponent(reviewId)}`);
  } catch (error) {
    if (error instanceof ServerApiError && (error.status === 404 || error.status === 403)) {
      return null;
    }
    throw error;
  }
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const data = await loadReview(id);
  if (!data) {
    return { title: "Review — auxd" };
  }
  const { review, user, album } = data;
  const handle = user?.handle ?? "user";
  const preview =
    review.body.length > 140 ? `${review.body.slice(0, 140).trimEnd()}…` : review.body;
  const title = `@${handle}'s review of ${album.title} — auxd`;
  const siteUrl = getSiteUrl();
  return {
    title,
    description: preview,
    openGraph: {
      title: `@${handle}'s review of ${album.title}`,
      description: preview,
      url: `${siteUrl}/review/${encodeURIComponent(review.id)}`,
      images: album.cover_art_url ? [{ url: album.cover_art_url }] : undefined,
    },
  };
}

export default async function ReviewPage({ params }: { params: Params }) {
  const { id } = await params;
  const data = await loadReview(id);
  if (!data) {
    notFound();
  }
  const { review, user, album, viewer_entry } = data;
  const shareUrl = `${getSiteUrl()}/review/${encodeURIComponent(review.id)}`;
  return (
    <ReviewReadingView
      review={review}
      user={user}
      album={album}
      viewerEntry={viewer_entry}
      shareUrl={shareUrl}
    />
  );
}
