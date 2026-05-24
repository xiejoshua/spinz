import { AlbumActions } from "@/components/album-detail/album-actions";
import { FriendsSection } from "@/components/album-detail/friends-section";
import { AlbumHero } from "@/components/album-detail/hero";
import { MyHistory } from "@/components/album-detail/my-history";
import { RatingHistogram } from "@/components/album-detail/rating-histogram";
import { ReviewsList } from "@/components/album-detail/reviews-list";
import { Tracklist } from "@/components/album-detail/tracklist";
import type { AlbumDetailResponse } from "@/lib/album-types";
import { ServerApiError, serverApiGet } from "@/lib/api-server";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

type Params = Promise<{ id: string }>;

async function loadAlbum(id: string): Promise<AlbumDetailResponse | null> {
  try {
    return await serverApiGet<AlbumDetailResponse>(`/api/v1/albums/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof ServerApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const data = await loadAlbum(id);
  if (!data) {
    return { title: "Album not found — auxd" };
  }
  const { album, aggregate } = data;
  const yearSuffix = album.release_year ? ` (${album.release_year})` : "";
  const ratingSuffix =
    aggregate.rating_count > 0
      ? ` · ${aggregate.avg_rating.toFixed(1)}★ from ${aggregate.rating_count} ${aggregate.rating_count === 1 ? "log" : "logs"}`
      : "";
  return {
    title: `${album.title} — ${album.artist_credit}${yearSuffix} · auxd`,
    description: `${album.artist_credit} — ${album.title}${yearSuffix}${ratingSuffix}`,
    openGraph: {
      title: `${album.title} — ${album.artist_credit}`,
      description: `${aggregate.rating_count} ${aggregate.rating_count === 1 ? "log" : "logs"} on auxd${ratingSuffix}`,
      images: [{ url: `/api/og/album/${encodeURIComponent(album.id)}` }],
    },
    twitter: { card: "summary_large_image" },
  };
}

export default async function AlbumDetailPage({ params }: { params: Params }) {
  const { id } = await params;
  const data = await loadAlbum(id);
  if (!data) {
    notFound();
  }

  const { album, editions, aggregate, friends, my_history } = data;
  const myEntry = my_history[0] ?? null;

  return (
    <article className="container max-w-3xl space-y-6 py-6">
      <AlbumHero album={album} aggregate={aggregate} editions={editions} />
      <AlbumActions album={album} myEntry={myEntry} />
      <RatingHistogram avgRating={aggregate.avg_rating} ratingCount={aggregate.rating_count} />
      <MyHistory history={my_history} />
      {album.tracklist.length > 0 && <Tracklist tracks={album.tracklist} />}
      <FriendsSection friends={friends} />
      <ReviewsList albumId={album.id} />
    </article>
  );
}
