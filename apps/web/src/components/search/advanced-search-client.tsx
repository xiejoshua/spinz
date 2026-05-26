"use client";

import { useCoverFilter } from "@/components/discover/use-cover-filter";
import { DECADE_VALUES, type Decade, DecadeChipRow } from "@/components/search/decade-chip-row";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type { DiscoverAlbumSummary } from "@/lib/social-types";
import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

const PAGE_SIZE = 24;
const DEBOUNCE_MS = 250;

type Sort =
  | "relevance"
  | "popular_on_auxd"
  | "recently_added"
  | "year_newest"
  | "year_oldest"
  | "surprise";
const VALID_SORTS: Sort[] = [
  "relevance",
  "popular_on_auxd",
  "recently_added",
  "year_newest",
  "year_oldest",
  "surprise",
];

const SORT_LABELS: Record<Sort, string> = {
  relevance: "Relevance",
  popular_on_auxd: "Popular on auxd",
  recently_added: "Recently added",
  year_newest: "Year — Newest",
  year_oldest: "Year — Oldest",
  surprise: "Surprise me",
};

type AdvancedSearchResponse = {
  results: DiscoverAlbumSummary[];
  total: number;
  has_more: boolean;
  report_missing_album_url?: string | null;
};

function parseDecadesParam(raw: string | null): Set<Decade> {
  if (!raw) return new Set();
  const set = new Set<Decade>();
  for (const token of raw.split(",")) {
    const cleaned = token.trim() as Decade;
    if ((DECADE_VALUES as ReadonlyArray<string>).includes(cleaned)) {
      set.add(cleaned);
    }
  }
  return set;
}

function serializeDecades(set: Set<Decade>): string | null {
  if (set.size === 0) return null;
  // Backend supports YYYYs tokens; "earlier" is a synthetic UI bucket
  // expanded into pre-1980 decades.
  const expanded: string[] = [];
  for (const d of set) {
    if (d === "earlier") {
      expanded.push("1970s", "1960s", "1950s", "1940s", "1930s", "1920s", "1910s", "1900s");
    } else {
      expanded.push(d);
    }
  }
  return expanded.join(",");
}

/**
 * Advanced album search surface — feature 003 / FR-015..FR-020.
 *
 * URL-driven: ``?q=&decade=&year_min=&year_max=&sort=`` so a result
 * page is shareable. Filter state is mirrored to the URL via
 * router.replace (no scroll) so the back button still steps through
 * history points the way the user expects.
 *
 * Uses TanStack Query's infinite-query helper for "Load more →"
 * pagination — fetches the next ``PAGE_SIZE`` slice from the backend,
 * appends to the result list, no scroll jump.
 */
export function AdvancedSearchClient() {
  const router = useRouter();
  const pathname = usePathname() ?? "/search";
  const searchParams = useSearchParams();

  const initialQuery = searchParams?.get("q") ?? "";
  const initialDecades = useMemo(
    () => parseDecadesParam(searchParams?.get("decade")),
    [searchParams]
  );
  const initialYearMin = searchParams?.get("year_min") ?? "";
  const initialYearMax = searchParams?.get("year_max") ?? "";
  const initialGenre = searchParams?.get("genre") ?? "";
  const initialSortRaw = (searchParams?.get("sort") ?? "relevance") as Sort;
  const initialSort: Sort = (VALID_SORTS as string[]).includes(initialSortRaw)
    ? initialSortRaw
    : "relevance";

  const [input, setInput] = useState(initialQuery);
  const [debounced, setDebounced] = useState(initialQuery);
  const [decades, setDecades] = useState<Set<Decade>>(initialDecades);
  const [yearMin, setYearMin] = useState(initialYearMin);
  const [yearMax, setYearMax] = useState(initialYearMax);
  const [genre, setGenre] = useState(initialGenre);
  const [debouncedGenre, setDebouncedGenre] = useState(initialGenre);
  const [sort, setSort] = useState<Sort>(initialSort);

  // Debounce the genre input so each keystroke doesn't fire a refetch.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedGenre(genre.trim()), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [genre]);

  // Debounce input → debounced.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(input.trim()), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [input]);

  // Mirror state to URL.
  const syncUrl = useCallback(() => {
    const params = new URLSearchParams();
    if (debounced) params.set("q", debounced);
    const decadesParam = serializeDecades(decades);
    if (decadesParam) params.set("decade", decadesParam);
    if (yearMin) params.set("year_min", yearMin);
    if (yearMax) params.set("year_max", yearMax);
    if (debouncedGenre) params.set("genre", debouncedGenre);
    if (sort !== "relevance") params.set("sort", sort);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [debounced, decades, yearMin, yearMax, debouncedGenre, sort, pathname, router]);

  useEffect(() => {
    syncUrl();
  }, [syncUrl]);

  const apiFilters = useMemo(() => {
    const params: Record<string, string | number | boolean> = {
      type: "album",
      limit: PAGE_SIZE,
      // Discover surfaces (this advanced grid included) hide coverless
      // rows — an empty cell reads as broken.
      require_cover: true,
    };
    if (debounced) params.q = debounced;
    const decadesParam = serializeDecades(decades);
    if (decadesParam) params.decade = decadesParam;
    if (yearMin) {
      const n = Number(yearMin);
      if (Number.isInteger(n) && n >= 1900 && n <= 2100) params.year_min = n;
    }
    if (yearMax) {
      const n = Number(yearMax);
      if (Number.isInteger(n) && n >= 1900 && n <= 2100) params.year_max = n;
    }
    if (debouncedGenre) params.genre = debouncedGenre;
    if (sort !== "relevance") params.sort = sort;
    return params;
  }, [debounced, decades, yearMin, yearMax, debouncedGenre, sort]);

  // Enable the query when EITHER the user has typed enough text OR
  // they've set at least one structured filter — this is the "browse
  // by decade / genre / year alone" path.
  const hasAnyFilter =
    decades.size > 0 || Boolean(yearMin) || Boolean(yearMax) || Boolean(debouncedGenre);
  const enabled = debounced.length >= 2 || hasAnyFilter;

  const query = useInfiniteQuery({
    queryKey: ["search", "advanced", apiFilters],
    enabled,
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const offset = pageParam as number;
      return apiClient.get<AdvancedSearchResponse>("/api/v1/search", {
        searchParams: { ...apiFilters, offset },
      });
    },
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage.has_more) return undefined;
      return allPages.reduce((acc, p) => acc + p.results.length, 0);
    },
    staleTime: 30 * 1000,
    // Keep the previous result set on screen while a new filter combo
    // is in flight. The user gets a "soft refresh" instead of a flash
    // back to skeletons every time they click a chip.
    placeholderData: keepPreviousData,
  });

  const allResults = useMemo(() => {
    return query.data?.pages.flatMap((p) => p.results) ?? [];
  }, [query.data]);
  const { visible: visibleResults, onCoverFailed } = useCoverFilter(allResults, (a) => a.id);
  const backendTotal = query.data?.pages[0]?.total ?? 0;
  // The backend ``total`` reflects post-server-filter count; client-side
  // cover failures shrink the visible set further, so the displayed
  // count tracks the visible list when it diverges.
  const total = visibleResults.length < allResults.length ? visibleResults.length : backendTotal;

  return (
    <div className="space-y-6">
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2"
          style={{ color: "var(--muted)" }}
        />
        <Input
          type="search"
          inputMode="search"
          autoFocus
          autoComplete="off"
          spellCheck={false}
          placeholder="Search the catalog…"
          aria-label="Search the album catalog"
          className="h-11 pl-9 pr-10 text-[15px]"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        {query.isFetching && enabled && (
          <Loader2
            aria-hidden="true"
            className="absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin"
            style={{ color: "var(--muted)" }}
          />
        )}
      </div>
      <FilterRow
        decades={decades}
        onDecadesChange={(next) => {
          setDecades(next);
          capture("search.advanced.filter_applied", {
            decades: Array.from(next),
            sort,
          });
        }}
        yearMin={yearMin}
        onYearMinChange={setYearMin}
        yearMax={yearMax}
        onYearMaxChange={setYearMax}
        genre={genre}
        onGenreChange={setGenre}
        sort={sort}
        onSortChange={(next) => {
          setSort(next);
          capture("search.advanced.filter_applied", {
            decades: Array.from(decades),
            sort: next,
          });
        }}
      />
      <Results
        enabled={enabled}
        query={debounced}
        results={visibleResults}
        onCoverFailed={onCoverFailed}
        total={total}
        loading={query.isFetching && visibleResults.length === 0}
        error={query.error}
        hasMore={query.hasNextPage ?? false}
        fetchingMore={query.isFetchingNextPage}
        onLoadMore={() => {
          capture("search.advanced.load_more", {
            offset: allResults.length,
            sort,
          });
          void query.fetchNextPage();
        }}
        reportMissingUrl={query.data?.pages[0]?.report_missing_album_url ?? null}
      />
    </div>
  );
}

function FilterRow({
  decades,
  onDecadesChange,
  yearMin,
  onYearMinChange,
  yearMax,
  onYearMaxChange,
  genre,
  onGenreChange,
  sort,
  onSortChange,
}: {
  decades: Set<Decade>;
  onDecadesChange: (next: Set<Decade>) => void;
  yearMin: string;
  onYearMinChange: (next: string) => void;
  yearMax: string;
  onYearMaxChange: (next: string) => void;
  genre: string;
  onGenreChange: (next: string) => void;
  sort: Sort;
  onSortChange: (next: Sort) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <DecadeChipRow selected={decades} onChange={onDecadesChange} />
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label
            htmlFor="search-year-min"
            className="font-mono uppercase"
            style={{
              fontSize: "10px",
              letterSpacing: "0.18em",
              color: "var(--muted)",
            }}
          >
            Year
          </label>
          <Input
            id="search-year-min"
            type="number"
            inputMode="numeric"
            placeholder="Min"
            aria-label="Year minimum"
            className="h-9 w-20 text-[13px]"
            min={1900}
            max={2100}
            value={yearMin}
            onChange={(e) => onYearMinChange(e.target.value)}
          />
          <span style={{ color: "var(--muted)" }}>–</span>
          <Input
            id="search-year-max"
            type="number"
            inputMode="numeric"
            placeholder="Max"
            aria-label="Year maximum"
            className="h-9 w-20 text-[13px]"
            min={1900}
            max={2100}
            value={yearMax}
            onChange={(e) => onYearMaxChange(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="search-genre"
            className="font-mono uppercase"
            style={{
              fontSize: "10px",
              letterSpacing: "0.18em",
              color: "var(--muted)",
            }}
          >
            Genre
          </label>
          <Input
            id="search-genre"
            type="text"
            placeholder="e.g. hip hop, jazz"
            aria-label="Filter by genre"
            className="h-9 w-44 text-[13px]"
            maxLength={60}
            value={genre}
            onChange={(e) => onGenreChange(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="search-sort"
            className="font-mono uppercase"
            style={{
              fontSize: "10px",
              letterSpacing: "0.18em",
              color: "var(--muted)",
            }}
          >
            Sort
          </label>
          <select
            id="search-sort"
            value={sort}
            onChange={(e) => onSortChange(e.target.value as Sort)}
            aria-label="Sort results"
            className="h-9 rounded-md px-2 font-sans text-[13px]"
            style={{
              background: "var(--field-background)",
              color: "var(--field-foreground)",
              border: "1px solid var(--field-border)",
              cursor: "pointer",
            }}
          >
            {(Object.entries(SORT_LABELS) as Array<[Sort, string]>).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

function Results({
  enabled,
  query,
  results,
  onCoverFailed,
  total,
  loading,
  error,
  hasMore,
  fetchingMore,
  onLoadMore,
  reportMissingUrl,
}: {
  enabled: boolean;
  query: string;
  results: DiscoverAlbumSummary[];
  onCoverFailed: (albumId: string) => void;
  total: number;
  loading: boolean;
  error: unknown;
  hasMore: boolean;
  fetchingMore: boolean;
  onLoadMore: () => void;
  reportMissingUrl: string | null;
}) {
  if (!enabled) {
    return (
      <p className="font-sans text-sm" style={{ color: "var(--muted)" }}>
        Type at least 2 characters, or pick a decade, genre, or year range to start browsing.
      </p>
    );
  }
  if (loading) {
    return <ResultsSkeleton />;
  }
  if (error) {
    return (
      <p className="font-sans text-sm" style={{ color: "var(--danger)" }}>
        Search failed. Try a different query or refresh the page.
      </p>
    );
  }
  if (results.length === 0) {
    return (
      <div className="space-y-2">
        <p className="font-sans text-sm" style={{ color: "var(--muted)" }}>
          {query
            ? `No matches for "${query}" with the current filters.`
            : "No albums match the current filters yet."}
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
  return (
    <div className="space-y-4">
      <p
        className="font-mono uppercase"
        style={{
          fontSize: "11px",
          letterSpacing: "0.18em",
          color: "var(--muted)",
        }}
      >
        {total === 0
          ? "No results"
          : results.length === total
            ? `${total} result${total === 1 ? "" : "s"}`
            : `Showing ${results.length} of ${total}${hasMore ? "+" : ""}`}
      </p>
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {results.map((album) => (
          <li key={album.id}>
            <ResultCard album={album} onCoverFailed={onCoverFailed} />
          </li>
        ))}
      </ul>
      {hasMore && (
        <div className="flex justify-center pt-2">
          <button
            type="button"
            onClick={onLoadMore}
            disabled={fetchingMore}
            className="search-load-more inline-flex items-center gap-2 rounded-md px-5 py-2 font-sans text-[13px] font-medium transition-colors"
            style={{
              background: "var(--surface-secondary)",
              color: "var(--foreground)",
              border: "1px solid var(--border)",
              cursor: fetchingMore ? "wait" : "pointer",
            }}
          >
            {fetchingMore ? (
              <>
                <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
                Loading…
              </>
            ) : (
              <>Load more →</>
            )}
          </button>
          <style>{`
            .search-load-more:hover:not(:disabled) { background: var(--surface-tertiary); }
            .search-load-more:focus-visible {
              outline: 2px solid var(--focus);
              outline-offset: 2px;
            }
          `}</style>
        </div>
      )}
    </div>
  );
}

function ResultCard({
  album,
  onCoverFailed,
}: {
  album: DiscoverAlbumSummary;
  onCoverFailed: (albumId: string) => void;
}) {
  const year = album.release_year ? album.release_year : null;
  return (
    <Link href={`/album/${album.id}`} className="search-result-card flex flex-col gap-2">
      <Cover album={album} onError={() => onCoverFailed(album.id)} />
      <div className="min-w-0">
        <p
          className="search-result-card__title truncate font-serif font-semibold leading-[1.2] tracking-[-0.005em]"
          style={{
            fontSize: "14px",
            fontFamily: "var(--font-serif)",
            color: "var(--foreground)",
          }}
        >
          {album.title}
        </p>
        <p className="truncate font-sans text-[12px]" style={{ color: "var(--muted)" }}>
          {album.artist_name}
          {year ? ` · ${year}` : ""}
        </p>
      </div>
      <style>{`
        .search-result-card { cursor: pointer; }
        .search-result-card:hover .search-result-card__title { color: var(--accent); }
        .search-result-card:focus-visible {
          outline: 2px solid var(--focus);
          outline-offset: 2px;
          border-radius: 2px;
        }
      `}</style>
    </Link>
  );
}

function Cover({
  album,
  onError,
}: {
  album: DiscoverAlbumSummary;
  onError?: () => void;
}) {
  const style = {
    background: "var(--surface-secondary)",
    aspectRatio: "1 / 1",
  } as const;
  if (album.mbid) {
    const fallback = album.cover_art_url
      ? `?fallback=${encodeURIComponent(album.cover_art_url)}`
      : "";
    return (
      <img
        src={`/api/cover/500/${album.mbid}${fallback}`}
        alt=""
        loading="lazy"
        onError={onError}
        className="w-full rounded object-cover"
        style={style}
      />
    );
  }
  if (album.cover_art_url) {
    return (
      <img
        src={album.cover_art_url}
        alt=""
        loading="lazy"
        onError={onError}
        className="w-full rounded object-cover"
        style={style}
      />
    );
  }
  return (
    <div
      aria-hidden="true"
      className="w-full rounded"
      style={{
        ...style,
        background: "linear-gradient(135deg, var(--surface-secondary), var(--surface-tertiary))",
      }}
    />
  );
}

function ResultsSkeleton() {
  return (
    <ul
      className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6"
      aria-hidden="true"
    >
      {Array.from({ length: PAGE_SIZE }, (_, i) => `skeleton-${i}`).map((id) => (
        <li key={id} className="flex flex-col gap-2">
          <div
            className="w-full rounded"
            style={{
              aspectRatio: "1 / 1",
              background: "var(--surface-secondary)",
            }}
          />
          <div className="h-3 w-3/4 rounded" style={{ background: "var(--surface-secondary)" }} />
          <div className="h-3 w-1/2 rounded" style={{ background: "var(--surface-secondary)" }} />
        </li>
      ))}
    </ul>
  );
}
