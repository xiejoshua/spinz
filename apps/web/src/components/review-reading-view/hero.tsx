import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import type { AlbumPayload, DiaryRow } from "@/lib/album-types";
import type { Review, ReviewUserCard } from "@/lib/review-types";
import Link from "next/link";

type Props = {
  review: Review;
  user: ReviewUserCard | undefined;
  album: AlbumPayload;
  /** The viewer's own diary entry for the album, if any — for rating context line. */
  viewerEntry: DiaryRow | null;
};

export function ReadingHero({ review, user, album, viewerEntry }: Props) {
  const coverUrl = album.mbid
    ? `/api/cover/500/${album.mbid}${album.cover_art_url ? `?fallback=${encodeURIComponent(album.cover_art_url)}` : ""}`
    : album.cover_art_url;
  return (
    <header className="space-y-4">
      <div className="flex items-start gap-4">
        <Link
          href={`/album/${encodeURIComponent(album.id)}`}
          aria-label={`Open ${album.title}`}
          className="block shrink-0"
        >
          {coverUrl ? (
            <img
              src={coverUrl}
              alt=""
              width={120}
              height={120}
              className="size-24 rounded bg-muted object-cover sm:size-32"
            />
          ) : (
            <div aria-hidden="true" className="size-24 rounded bg-muted sm:size-32" />
          )}
        </Link>
        <div className="min-w-0 flex-1 space-y-1">
          <Link href={`/album/${encodeURIComponent(album.id)}`} className="block hover:underline">
            <h2 className="truncate text-lg font-semibold leading-tight">{album.title}</h2>
          </Link>
          <p className="truncate text-sm text-muted-foreground">
            {album.artist_credit}
            {album.release_year ? ` · ${album.release_year}` : ""}
          </p>
          {viewerEntry && (
            <p className="pt-1 text-xs text-muted-foreground">
              {viewerEntry.rating != null ? (
                <>
                  You rated this{" "}
                  <span aria-hidden="true" className="text-foreground">
                    {"★".repeat(Math.round(viewerEntry.rating))}
                  </span>
                  <span className="sr-only">{viewerEntry.rating} of 5 stars</span>
                </>
              ) : (
                "You logged this without a rating"
              )}
              {viewerEntry.auxed && (
                <>
                  {" · "}
                  <span aria-hidden="true">🏅</span> Aux’d
                </>
              )}
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 border-t pt-3">
        <Avatar className="size-8">
          <AvatarFallback>
            {(user?.handle ?? review.user_id).slice(0, 2).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1 leading-tight">
          <p className="truncate text-sm font-medium">
            {user?.display_name ?? user?.handle ?? `User ${review.user_id.slice(0, 8)}`}
          </p>
          <p className="truncate text-xs text-muted-foreground">@{user?.handle ?? "unknown"}</p>
        </div>
        {review.edited_at && (
          <Badge variant="outline" className="h-5 px-1.5 py-0 text-[10px]">
            edited
          </Badge>
        )}
      </div>
    </header>
  );
}
