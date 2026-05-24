import { AuxIcon } from "@/components/icons/aux";
import { Badge } from "@/components/ui/badge";
import type { AlbumAggregate, AlbumPayload } from "@/lib/album-types";
import { EditionSelector } from "./edition-selector";

type Props = {
  album: AlbumPayload;
  aggregate: AlbumAggregate;
  editions: AlbumPayload[];
};

export function AlbumHero({ album, aggregate, editions }: Props) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row">
      <CoverArt album={album} />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h1 className="text-2xl font-bold leading-tight tracking-tight">{album.title}</h1>
        </div>
        <p className="text-muted-foreground">
          {album.artist_credit}
          {album.release_year ? ` · ${album.release_year}` : ""}
        </p>
        <div className="flex flex-wrap gap-2 pt-1">
          {album.genres.slice(0, 3).map((g) => (
            <Badge key={g} variant="secondary">
              {g}
            </Badge>
          ))}
          {editions.length > 1 && <EditionSelector editions={editions} currentId={album.id} />}
        </div>
        <AggregateRow aggregate={aggregate} />
      </div>
    </header>
  );
}

function CoverArt({ album }: { album: AlbumPayload }) {
  const size = 220;
  const src = album.mbid
    ? `/api/cover/500/${album.mbid}${album.cover_art_url ? `?fallback=${encodeURIComponent(album.cover_art_url)}` : ""}`
    : album.cover_art_url;
  if (!src) {
    return (
      <div
        aria-hidden="true"
        className="size-44 shrink-0 self-start rounded-md bg-muted sm:size-56"
      />
    );
  }
  return (
    <img
      src={src}
      alt={`Cover of ${album.title}`}
      width={size}
      height={size}
      className="size-44 shrink-0 self-start rounded-md bg-muted object-cover sm:size-56"
    />
  );
}

function AggregateRow({ aggregate }: { aggregate: AlbumAggregate }) {
  if (aggregate.rating_count === 0) {
    return (
      <p className="pt-1 text-sm text-muted-foreground">
        No logs yet — be the first to rate this album.
      </p>
    );
  }
  const stars = "★".repeat(Math.round(aggregate.avg_rating));
  return (
    <dl className="flex flex-wrap gap-x-6 gap-y-1 pt-1 text-sm">
      <div>
        <dt className="sr-only">Average rating</dt>
        <dd>
          <span aria-hidden="true" className="font-medium">
            {stars || "—"}
          </span>{" "}
          <span className="text-muted-foreground">
            {aggregate.avg_rating.toFixed(1)} from {aggregate.rating_count}
          </span>
        </dd>
      </div>
      {aggregate.aux_count > 0 && (
        <div>
          <dt className="sr-only">Aux’d count</dt>
          <dd>
            <span
              aria-hidden="true"
              className="inline-flex items-center align-text-bottom"
              style={{ color: "var(--gold)" }}
            >
              <AuxIcon filled size={14} />
            </span>{" "}
            {aggregate.aux_count}
          </dd>
        </div>
      )}
      {aggregate.review_count > 0 && (
        <div>
          <dt className="sr-only">Reviews</dt>
          <dd className="text-muted-foreground">
            {aggregate.review_count} {aggregate.review_count === 1 ? "review" : "reviews"}
          </dd>
        </div>
      )}
    </dl>
  );
}
