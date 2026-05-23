"use client";

import { SearchInput } from "@/components/search/search-input";
import { SearchResults } from "@/components/search/search-results";
import { apiClient } from "@/lib/api-client";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

export type SearchAlbum = {
  mbid: string | null;
  discogs_release_id: string | null;
  title: string;
  artist_name: string;
  release_year: number | null;
  cover_art_url: string | null;
};

export type SearchResponse = {
  results: SearchAlbum[];
  report_missing_album_url?: string;
};

const DEBOUNCE_MS = 200;
const MIN_QUERY_LEN = 3;

export function SearchClient() {
  const [input, setInput] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(input.trim()), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [input]);

  const enabled = debounced.length >= MIN_QUERY_LEN;

  const { data, isFetching, error } = useQuery({
    queryKey: ["search", "album", debounced],
    queryFn: () =>
      apiClient.get<SearchResponse>("/api/v1/search", {
        searchParams: { q: debounced, type: "album", limit: 10 },
      }),
    enabled,
    staleTime: 30 * 1000,
  });

  return (
    <div className="space-y-4">
      <SearchInput value={input} onChange={setInput} loading={isFetching && enabled} />
      <SearchResults
        query={debounced}
        results={data?.results ?? []}
        reportMissingUrl={data?.report_missing_album_url ?? null}
        error={error}
        minQueryLen={MIN_QUERY_LEN}
        searched={enabled && !isFetching}
      />
    </div>
  );
}
