"use client";

import type { SearchAlbum, SearchResponse } from "@/components/search/search-client";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type { LogSheetSeed } from "@/stores/ui";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRecentLogSearches } from "./recent-searches";

const DEBOUNCE_MS = 200;
const MIN_QUERY_LEN = 3;

type Props = {
  onPick: (seed: LogSheetSeed) => void;
};

function albumToSeed(album: SearchAlbum): LogSheetSeed {
  // album_id is the materialised Album row's KSUID — search hits are
  // resolved via identity.resolve_identity before the response is sent,
  // so every hit carries a stable id. Discogs-master-only hits (no MBID,
  // no release_id) used to be unloggable; now we route through the KSUID
  // and the backend looks the row up directly.
  return {
    album_id: album.id,
    mbid: album.mbid,
    title: album.title,
    artist_credit: album.artist_name,
    cover_art_url: album.cover_art_url,
  };
}

export function AlbumSearch({ onPick }: Props) {
  const [input, setInput] = useState("");
  const [debounced, setDebounced] = useState("");
  const { recent, push } = useRecentLogSearches();

  useEffect(() => {
    const t = setTimeout(() => setDebounced(input.trim()), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [input]);

  const enabled = debounced.length >= MIN_QUERY_LEN;

  const { data, isFetching } = useQuery({
    queryKey: ["log-sheet-search", debounced],
    queryFn: () =>
      apiClient.get<SearchResponse>("/api/v1/search", {
        searchParams: { q: debounced, type: "album", limit: 8 },
      }),
    enabled,
    staleTime: 30 * 1000,
  });

  function handlePick(album: SearchAlbum, atIndex: number) {
    const seed = albumToSeed(album);
    push({ ...seed, query: debounced, artist_name: album.artist_name });
    capture("log.search_accepted", {
      query_length: debounced.length,
      result_index: atIndex,
      had_mbid: album.mbid !== null,
    });
    onPick(seed);
  }

  return (
    <div className="mt-4 space-y-3">
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="search"
          inputMode="search"
          autoFocus
          autoComplete="off"
          spellCheck={false}
          placeholder="Search for an album…"
          aria-label="Search album"
          className="pl-9 pr-10"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        {isFetching && enabled && (
          <Loader2
            aria-hidden="true"
            className="absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin text-muted-foreground"
          />
        )}
      </div>

      {!enabled && recent.length > 0 && (
        <RecentList recent={recent} onPick={(seed) => onPick(seed)} />
      )}

      {enabled && data && data.results.length === 0 && !isFetching && (
        <div className="rounded-md border p-3 text-sm space-y-2">
          <p className="text-muted-foreground">
            No matches for <span className="text-foreground">“{debounced}”</span>.
          </p>
          {data.report_missing_album_url && (
            <Link href={data.report_missing_album_url} className="font-medium underline">
              Report missing album
            </Link>
          )}
        </div>
      )}

      {enabled && data && data.results.length > 0 && (
        <ul
          className="divide-y rounded-md border max-h-64 overflow-y-auto"
          aria-label="Album results"
        >
          {data.results.map((album, i) => {
            const seed = albumToSeed(album);
            return (
              <li key={album.id}>
                <button
                  type="button"
                  disabled={!seed}
                  onClick={() => handlePick(album, i)}
                  className="flex w-full items-center gap-3 p-2 text-left hover:bg-muted disabled:opacity-50"
                >
                  <CoverThumb album={album} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{album.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {album.artist_name}
                      {album.release_year ? ` · ${album.release_year}` : ""}
                    </p>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function RecentList({
  recent,
  onPick,
}: {
  recent: (LogSheetSeed & { query: string })[];
  onPick: (seed: LogSheetSeed) => void;
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Recent</p>
      <ul className="divide-y rounded-md border">
        {recent.map((seed) => (
          <li key={seed.album_id}>
            <button
              type="button"
              onClick={() => onPick(seed)}
              className="flex w-full items-center gap-3 p-2 text-left hover:bg-muted"
            >
              <CoverThumb
                album={{
                  id: seed.album_id,
                  mbid: seed.mbid,
                  discogs_release_id: null,
                  title: seed.title,
                  artist_name: seed.artist_credit,
                  release_year: null,
                  cover_art_url: seed.cover_art_url,
                }}
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{seed.title}</p>
                <p className="truncate text-xs text-muted-foreground">{seed.artist_credit}</p>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CoverThumb({ album }: { album: SearchAlbum }) {
  if (album.mbid) {
    const fallback = album.cover_art_url
      ? `?fallback=${encodeURIComponent(album.cover_art_url)}`
      : "";
    return (
      <img
        src={`/api/cover/250/${album.mbid}${fallback}`}
        alt=""
        width={40}
        height={40}
        loading="lazy"
        className="size-10 shrink-0 rounded bg-muted object-cover"
      />
    );
  }
  if (album.cover_art_url) {
    return (
      <img
        src={album.cover_art_url}
        alt=""
        width={40}
        height={40}
        loading="lazy"
        className="size-10 shrink-0 rounded bg-muted object-cover"
      />
    );
  }
  return <div aria-hidden="true" className="size-10 shrink-0 rounded bg-muted" />;
}
