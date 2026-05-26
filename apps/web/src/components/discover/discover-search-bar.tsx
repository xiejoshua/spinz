"use client";

import { useCoverFilter } from "@/components/discover/use-cover-filter";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type {
  DiscoverAlbumSummary,
  UserSearchResponse,
  UserSearchResult,
} from "@/lib/social-types";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Mode = "people" | "albums";
const VALID_MODES: Mode[] = ["people", "albums"];

const MIN_QUERY_LEN = 2;
const DEBOUNCE_MS = 200;
// Dropdown caps at 5; the "More results in advanced search →" CTA in
// the dropdown footer handles "I want more" without crowding the
// quick-lookup surface.
const MAX_RESULTS = 5;

type AlbumSearchResponse = {
  results: DiscoverAlbumSummary[];
  report_missing_album_url?: string | null;
};

/**
 * Top-of-page Discover search — single input with a People/Albums
 * toggle pill. Autocompletes both entities below the input; selecting
 * an entry routes to the entity page. Albums mode also surfaces a
 * "More results in advanced search →" CTA pointing at /search with
 * the current query carried in the URL.
 *
 * URL ownership: ``?mode=people|albums`` persists the toggle across
 * reloads. Query text is intentionally NOT mirrored to the URL — the
 * Discover front page is not a search results surface; that's what
 * /search is for.
 */
export function DiscoverSearchBar() {
  const router = useRouter();
  const pathname = usePathname() ?? "/discover";
  const searchParams = useSearchParams();

  const initialMode = useMemo<Mode>(() => {
    const raw = searchParams?.get("mode");
    return (VALID_MODES as string[]).includes(raw ?? "") ? ((raw as Mode) ?? "people") : "people";
  }, [searchParams]);

  const [mode, setMode] = useState<Mode>(initialMode);
  const [input, setInput] = useState("");
  const [debounced, setDebounced] = useState("");
  const [focused, setFocused] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Sync URL when the user toggles modes.
  const onModeChange = useCallback(
    (next: Mode) => {
      if (next === mode) return;
      setMode(next);
      const params = new URLSearchParams(searchParams?.toString() ?? "");
      if (next === "people") {
        params.delete("mode");
      } else {
        params.set("mode", next);
      }
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
      capture("discover.search.mode_toggle", { mode: next });
    },
    [mode, pathname, router, searchParams]
  );

  // Debounce input → debounced.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(input.trim()), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [input]);

  // Reset input when the toggle changes so we don't show stale results
  // from the previous mode while the user is typing again.
  useEffect(() => {
    setInput("");
    setDebounced("");
  }, []);

  const enabled = debounced.length >= MIN_QUERY_LEN;

  const peopleQuery = useQuery({
    queryKey: ["discover", "search", "people", debounced],
    enabled: enabled && mode === "people",
    queryFn: () =>
      apiClient.get<UserSearchResponse>("/api/v1/users/search", {
        searchParams: { q: debounced, limit: MAX_RESULTS },
      }),
    staleTime: 30 * 1000,
  });

  const albumsQuery = useQuery({
    queryKey: ["discover", "search", "albums", debounced],
    enabled: enabled && mode === "albums",
    queryFn: () =>
      apiClient.get<AlbumSearchResponse>("/api/v1/search", {
        searchParams: {
          q: debounced,
          type: "album",
          limit: MAX_RESULTS,
          // Discover surfaces hide coverless rows — see the backend
          // ``require_cover`` flag for the rationale.
          require_cover: true,
        },
      }),
    staleTime: 30 * 1000,
  });

  // Close the dropdown when the user clicks outside.
  useEffect(() => {
    if (!focused) return;
    const onDown = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) {
        setFocused(false);
      }
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [focused]);

  const showDropdown = focused && enabled;
  const loading =
    mode === "people" ? peopleQuery.isFetching && enabled : albumsQuery.isFetching && enabled;

  const placeholder = mode === "people" ? "Find people by handle or name…" : "Search the catalog…";

  return (
    <div ref={containerRef} className="relative">
      <ModeToggle value={mode} onChange={onModeChange} />
      <div className="relative mt-3">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2"
          style={{ color: "var(--muted)" }}
        />
        <Input
          type="search"
          inputMode="search"
          autoComplete="off"
          spellCheck={false}
          placeholder={placeholder}
          aria-label={mode === "people" ? "Search people" : "Search albums"}
          className="h-11 pl-9 pr-10 text-[15px]"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onFocus={() => setFocused(true)}
        />
        {loading && (
          <Loader2
            aria-hidden="true"
            className="absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin"
            style={{ color: "var(--muted)" }}
          />
        )}
      </div>
      {showDropdown && (
        <ResultsDropdown
          mode={mode}
          query={debounced}
          peopleResults={peopleQuery.data?.results ?? []}
          albumResults={albumsQuery.data?.results ?? []}
          peopleLoading={peopleQuery.isFetching}
          albumsLoading={albumsQuery.isFetching}
          onSelect={() => setFocused(false)}
        />
      )}
    </div>
  );
}

function ModeToggle({
  value,
  onChange,
}: {
  value: Mode;
  onChange: (next: Mode) => void;
}) {
  return (
    <div role="radiogroup" aria-label="Search type" className="flex items-center gap-3">
      {(["people", "albums"] as Mode[]).map((m, i) => {
        const active = m === value;
        return (
          <span key={m} className="flex items-center gap-3">
            {i > 0 && (
              <span
                aria-hidden="true"
                className="font-mono"
                style={{ color: "var(--muted)", fontSize: "11px" }}
              >
                ·
              </span>
            )}
            <button
              type="button"
              // biome-ignore lint/a11y/useSemanticElements: visual toggle, not a form input
              role="radio"
              aria-checked={active}
              onClick={() => onChange(m)}
              className="discover-mode-eyebrow cursor-pointer font-mono uppercase transition-colors"
              style={{
                fontSize: "11px",
                letterSpacing: "0.18em",
                color: active ? "var(--accent)" : "var(--muted)",
                fontWeight: active ? 600 : 500,
                background: "transparent",
                padding: 0,
                border: "none",
              }}
            >
              {m === "people" ? "People" : "Albums"}
            </button>
          </span>
        );
      })}
      <style>{`
        .discover-mode-eyebrow:focus-visible {
          outline: 2px solid var(--focus);
          outline-offset: 4px;
        }
      `}</style>
    </div>
  );
}

function ResultsDropdown({
  mode,
  query,
  peopleResults,
  albumResults,
  peopleLoading,
  albumsLoading,
  onSelect,
}: {
  mode: Mode;
  query: string;
  peopleResults: UserSearchResult[];
  albumResults: DiscoverAlbumSummary[];
  peopleLoading: boolean;
  albumsLoading: boolean;
  onSelect: () => void;
}) {
  if (mode === "people") {
    return (
      <PeopleResultsList
        query={query}
        results={peopleResults}
        loading={peopleLoading}
        onSelect={onSelect}
      />
    );
  }
  return (
    <AlbumResultsList
      query={query}
      results={albumResults}
      loading={albumsLoading}
      onSelect={onSelect}
    />
  );
}

function PeopleResultsList({
  query,
  results,
  loading,
  onSelect,
}: {
  query: string;
  results: UserSearchResult[];
  loading: boolean;
  onSelect: () => void;
}) {
  if (loading && results.length === 0) {
    return <DropdownShell>{null}</DropdownShell>;
  }
  if (results.length === 0) {
    return (
      <DropdownShell>
        <p className="px-3 py-4 font-sans text-[13px]" style={{ color: "var(--muted)" }}>
          No people matching "{query}".
        </p>
      </DropdownShell>
    );
  }
  return (
    <DropdownShell>
      <ul aria-label="People search results">
        {results.map((u, index) => (
          <li
            key={u.id}
            style={{
              borderBottom: index === results.length - 1 ? "none" : "1px solid var(--separator)",
            }}
          >
            <Link
              href={`/profile/${encodeURIComponent(u.handle)}`}
              onClick={() => {
                capture("discover.search.user_clicked", {
                  result_position: index,
                  result_handle: u.handle,
                });
                onSelect();
              }}
              className="discover-search-row flex items-center gap-3 px-3 py-2.5"
            >
              <Avatar className="size-9">
                {u.avatar_url && <AvatarImage src={u.avatar_url} alt="" />}
                <AvatarFallback>{u.handle.slice(0, 2).toUpperCase()}</AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <p
                  className="discover-search-row__title truncate font-sans text-[14px] font-medium"
                  style={{ color: "var(--foreground)" }}
                >
                  {u.display_name || u.handle}
                </p>
                <p
                  className="discover-search-row__meta truncate font-sans text-[12px]"
                  style={{ color: "var(--muted)" }}
                >
                  @{u.handle}
                </p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </DropdownShell>
  );
}

function AlbumResultsList({
  query,
  results,
  loading,
  onSelect,
}: {
  query: string;
  results: DiscoverAlbumSummary[];
  loading: boolean;
  onSelect: () => void;
}) {
  const { visible, onCoverFailed } = useCoverFilter(results, (a) => a.id);
  if (loading && visible.length === 0) {
    return <DropdownShell>{null}</DropdownShell>;
  }
  return (
    <DropdownShell>
      {visible.length === 0 ? (
        <p className="px-3 py-4 font-sans text-[13px]" style={{ color: "var(--muted)" }}>
          No albums matching "{query}".
        </p>
      ) : (
        <ul aria-label="Album search results">
          {visible.map((a) => (
            <li
              key={a.id}
              style={{
                borderBottom: "1px solid var(--separator)",
              }}
            >
              <Link
                href={`/album/${a.id}`}
                onClick={onSelect}
                className="discover-search-row flex items-center gap-3 px-3 py-2.5"
              >
                <AlbumThumb album={a} onError={() => onCoverFailed(a.id)} />
                <div className="min-w-0 flex-1">
                  <p
                    className="discover-search-row__title truncate font-serif text-[15px] font-semibold tracking-[-0.005em]"
                    style={{
                      color: "var(--foreground)",
                      fontFamily: "var(--font-serif)",
                    }}
                  >
                    {a.title}
                  </p>
                  <p
                    className="discover-search-row__meta truncate font-sans text-[12px]"
                    style={{ color: "var(--muted)" }}
                  >
                    {a.artist_name}
                    {a.release_year ? ` · ${a.release_year}` : ""}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Link
        href={`/search?q=${encodeURIComponent(query)}`}
        onClick={() => {
          capture("discover.cta.advanced_search", { source: "albums_dropdown" });
          onSelect();
        }}
        className="discover-search-cta flex items-center justify-between px-3 py-2.5 font-sans text-[13px]"
        style={{
          color: "var(--accent)",
          background: "var(--surface-secondary)",
        }}
      >
        <span>More results in advanced search</span>
        <span aria-hidden="true">→</span>
      </Link>
    </DropdownShell>
  );
}

function AlbumThumb({
  album,
  onError,
}: {
  album: DiscoverAlbumSummary;
  onError?: () => void;
}) {
  const classes = "size-10 shrink-0 rounded object-cover";
  const baseStyle = { background: "var(--surface-secondary)" } as const;
  if (album.mbid) {
    const fallback = album.cover_art_url
      ? `?fallback=${encodeURIComponent(album.cover_art_url)}`
      : "";
    return (
      <img
        src={`/api/cover/250/${album.mbid}${fallback}`}
        alt=""
        loading="lazy"
        onError={onError}
        className={classes}
        style={baseStyle}
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
        className={classes}
        style={baseStyle}
      />
    );
  }
  return <div aria-hidden="true" className={classes} style={baseStyle} />;
}

function DropdownShell({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="absolute left-0 right-0 z-30 mt-1 overflow-hidden rounded-md"
      style={{
        background: "var(--overlay)",
        border: "1px solid var(--border)",
        boxShadow: "var(--overlay-shadow)",
      }}
    >
      {children}
      <style>{`
        .discover-search-row { transition: background 150ms; color: var(--foreground); }
        .discover-search-row:hover { background: var(--surface-hover); }
        .discover-search-row:focus-visible {
          outline: 2px solid var(--focus);
          outline-offset: -2px;
        }
        .discover-search-cta:hover { background: var(--surface-tertiary); }
        .discover-search-cta:focus-visible {
          outline: 2px solid var(--focus);
          outline-offset: -2px;
        }
      `}</style>
    </div>
  );
}
