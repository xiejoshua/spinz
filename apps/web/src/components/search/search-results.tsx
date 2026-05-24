"use client";

import type { SearchAlbum } from "@/components/search/search-client";
import { ApiError } from "@/lib/api-client";
import Link from "next/link";

type Props = {
  query: string;
  results: SearchAlbum[];
  reportMissingUrl: string | null;
  error: Error | null;
  minQueryLen: number;
  searched: boolean;
};

export function SearchResults({
  query,
  results,
  reportMissingUrl,
  error,
  minQueryLen,
  searched,
}: Props) {
  if (query.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Type at least {minQueryLen} characters to start searching.
      </p>
    );
  }
  if (query.length > 0 && query.length < minQueryLen) {
    return (
      <p className="text-sm text-muted-foreground">
        Keep typing… (at least {minQueryLen} characters)
      </p>
    );
  }
  if (error) {
    const detail = error instanceof ApiError ? error.message : "Network error";
    return <p className="text-sm text-destructive">Search failed — {detail}.</p>;
  }
  if (searched && results.length === 0) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">
          No matches for <span className="text-foreground">“{query}”</span>.
        </p>
        {reportMissingUrl && (
          <Link href={reportMissingUrl} className="text-sm font-medium underline">
            Report missing album
          </Link>
        )}
      </div>
    );
  }
  if (results.length === 0) {
    return null;
  }
  return (
    <ul className="divide-y rounded-md border" aria-label="Search results">
      {results.map((album) => {
        const year = album.release_year ? ` · ${album.release_year}` : "";
        return (
          <li key={album.id}>
            <Link
              href={`/album/${album.id}`}
              className="flex items-center gap-3 p-3 hover:bg-muted"
            >
              <CoverThumb album={album} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{album.title}</p>
                <p className="truncate text-sm text-muted-foreground">
                  {album.artist_name}
                  {year}
                </p>
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function CoverThumb({ album }: { album: SearchAlbum }) {
  const size = 64;
  if (album.mbid) {
    const fallback = album.cover_art_url
      ? `?fallback=${encodeURIComponent(album.cover_art_url)}`
      : "";
    return (
      <img
        src={`/api/cover/250/${album.mbid}${fallback}`}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        className="size-12 rounded bg-muted object-cover"
      />
    );
  }
  if (album.cover_art_url) {
    return (
      <img
        src={album.cover_art_url}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        className="size-12 rounded bg-muted object-cover"
      />
    );
  }
  return <div aria-hidden="true" className="size-12 rounded bg-muted" />;
}
