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
      <p className="font-sans text-sm" style={{ color: "var(--muted)" }}>
        Type at least {minQueryLen} characters to start searching.
      </p>
    );
  }
  if (query.length > 0 && query.length < minQueryLen) {
    return (
      <p className="font-sans text-sm" style={{ color: "var(--muted)" }}>
        Keep typing… (at least {minQueryLen} characters)
      </p>
    );
  }
  if (error) {
    const detail = error instanceof ApiError ? error.message : "Network error";
    return (
      <p className="font-sans text-sm" style={{ color: "var(--danger)" }}>
        Search failed — {detail}.
      </p>
    );
  }
  if (searched && results.length === 0) {
    return (
      <div className="space-y-2">
        <p className="font-sans text-sm" style={{ color: "var(--muted)" }}>
          No matches for{" "}
          <span style={{ color: "var(--foreground)" }}>"{query}"</span>.
        </p>
        {reportMissingUrl && (
          <Link
            href={reportMissingUrl}
            className="font-sans text-sm font-medium underline"
            style={{ color: "var(--link)" }}
          >
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
    <>
      <ul
        className="overflow-hidden rounded-md"
        style={{ border: "1px solid var(--border)" }}
        aria-label="Search results"
      >
        {results.map((album, i) => {
          const year = album.release_year ? ` · ${album.release_year}` : "";
          const isLast = i === results.length - 1;
          return (
            <li
              key={album.id}
              style={{
                borderBottom: isLast ? "none" : "1px solid var(--separator)",
              }}
            >
              <Link
                href={`/album/${album.id}`}
                className="search-result-row flex items-center gap-3 p-3 transition-colors"
              >
                <CoverThumb album={album} />
                <div className="min-w-0 flex-1">
                  <p
                    className="search-result-row__title truncate font-serif font-semibold tracking-[-0.005em]"
                    style={{
                      fontSize: "16px",
                      fontFamily: "var(--font-serif)",
                    }}
                  >
                    {album.title}
                  </p>
                  <p className="search-result-row__meta truncate font-sans text-[13px]">
                    {album.artist_name}
                    {year}
                  </p>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
      <style>{`
        .search-result-row {
          color: var(--foreground);
          background: transparent;
        }
        .search-result-row .search-result-row__title { color: var(--foreground); }
        .search-result-row .search-result-row__meta  { color: var(--muted); }
        @media (hover: hover) {
          .search-result-row:hover {
            background: var(--accent);
            color: var(--accent-foreground);
          }
          .search-result-row:hover .search-result-row__title,
          .search-result-row:hover .search-result-row__meta {
            color: var(--accent-foreground);
          }
        }
        .search-result-row:focus-visible {
          outline: 2px solid var(--focus);
          outline-offset: -2px;
        }
      `}</style>
    </>
  );
}

function CoverThumb({ album }: { album: SearchAlbum }) {
  const size = 64;
  const classes = "size-12 shrink-0 rounded object-cover";
  const style = { background: "var(--surface-secondary)" };
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
        className={classes}
        style={style}
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
        className={classes}
        style={style}
      />
    );
  }
  return (
    <div
      aria-hidden="true"
      className="size-12 shrink-0 rounded"
      style={{
        background:
          "linear-gradient(135deg, var(--surface-secondary), var(--surface-tertiary))",
      }}
    />
  );
}
