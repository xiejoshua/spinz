"use client";

import type { SearchAlbum, SearchResponse } from "@/components/search/search-client";
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
    <div className="space-y-4">
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2"
          style={{ color: "var(--muted)" }}
        />
        <input
          type="search"
          inputMode="search"
          autoFocus
          autoComplete="off"
          spellCheck={false}
          placeholder="Album or artist…"
          aria-label="Search album"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="block w-full rounded-md py-3 pl-10 pr-10 font-sans text-[15px] focus:outline-none"
          style={{
            background: "var(--field-background)",
            color: "var(--field-foreground)",
            border: "1px solid var(--field-border)",
          }}
        />
        {isFetching && enabled && (
          <Loader2
            aria-hidden="true"
            className="absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin"
            style={{ color: "var(--muted)" }}
          />
        )}
      </div>

      {!enabled && recent.length > 0 && (
        <RecentList recent={recent} onPick={(seed) => onPick(seed)} />
      )}

      {enabled && data && data.results.length === 0 && !isFetching && (
        <div
          className="space-y-2 rounded-md p-4 font-sans text-sm"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            color: "var(--muted)",
          }}
        >
          <p>
            No matches for{" "}
            <span style={{ color: "var(--foreground)" }}>"{debounced}"</span>.
          </p>
          {data.report_missing_album_url && (
            <Link
              href={data.report_missing_album_url}
              className="font-medium hover:underline"
              style={{ color: "var(--link)" }}
            >
              Report missing album
            </Link>
          )}
        </div>
      )}

      {enabled && data && data.results.length > 0 && (
        <ResultsList
          results={data.results}
          eyebrow={`${data.results.length} ${data.results.length === 1 ? "result" : "results"} · MusicBrainz`}
          onPick={(album, i) => handlePick(album, i)}
        />
      )}
    </div>
  );
}

function ResultsList({
  results,
  eyebrow,
  onPick,
}: {
  results: SearchAlbum[];
  eyebrow: string;
  onPick: (album: SearchAlbum, atIndex: number) => void;
}) {
  return (
    <div>
      <SectionEyebrow text={eyebrow} />
      <ul
        className="overflow-y-auto rounded-md"
        style={{
          border: "1px solid var(--border)",
          maxHeight: "260px",
        }}
        aria-label="Album results"
      >
        {results.map((album, i) => (
          <li
            key={album.id}
            style={{
              borderBottom:
                i < results.length - 1 ? "1px solid var(--separator)" : "none",
            }}
          >
            <button
              type="button"
              onClick={() => onPick(album, i)}
              className="flex w-full cursor-pointer items-center gap-3 px-3 py-2.5 text-left transition-colors"
              style={{ color: "var(--foreground)" }}
            >
              <CoverThumb album={album} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-serif text-[15px] font-semibold tracking-[-0.005em]" style={{ fontFamily: "var(--font-serif)" }}>
                  {album.title}
                </p>
                <p
                  className="truncate font-sans text-[12px]"
                  style={{ color: "var(--muted)" }}
                >
                  {album.artist_name}
                  {album.release_year ? ` · ${album.release_year}` : ""}
                </p>
              </div>
            </button>
          </li>
        ))}
      </ul>
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
    <div>
      <SectionEyebrow text="Recent" />
      <ul
        className="rounded-md"
        style={{ border: "1px solid var(--border)" }}
      >
        {recent.map((seed, i) => (
          <li
            key={seed.album_id}
            style={{
              borderBottom:
                i < recent.length - 1 ? "1px solid var(--separator)" : "none",
            }}
          >
            <button
              type="button"
              onClick={() => onPick(seed)}
              className="flex w-full cursor-pointer items-center gap-3 px-3 py-2.5 text-left transition-colors"
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
                <p
                  className="truncate font-serif text-[15px] font-semibold tracking-[-0.005em]"
                  style={{
                    fontFamily: "var(--font-serif)",
                    color: "var(--foreground)",
                  }}
                >
                  {seed.title}
                </p>
                <p
                  className="truncate font-sans text-[12px]"
                  style={{ color: "var(--muted)" }}
                >
                  {seed.artist_credit}
                </p>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SectionEyebrow({ text }: { text: string }) {
  return (
    <p
      className="mb-2 font-mono uppercase"
      style={{
        fontSize: "11px",
        letterSpacing: "0.15em",
        color: "var(--muted)",
      }}
    >
      {text}
    </p>
  );
}

function CoverThumb({ album }: { album: SearchAlbum }) {
  const wrap = (src: string) => (
    <img
      src={src}
      alt=""
      width={44}
      height={44}
      loading="lazy"
      className="size-11 shrink-0 rounded object-cover"
      style={{ background: "var(--surface-secondary)" }}
    />
  );
  if (album.mbid) {
    const fallback = album.cover_art_url
      ? `?fallback=${encodeURIComponent(album.cover_art_url)}`
      : "";
    return wrap(`/api/cover/250/${album.mbid}${fallback}`);
  }
  if (album.cover_art_url) return wrap(album.cover_art_url);
  return (
    <div
      aria-hidden="true"
      className="size-11 shrink-0 rounded"
      style={{
        background:
          "linear-gradient(135deg, var(--surface-secondary), var(--surface-tertiary))",
      }}
    />
  );
}
