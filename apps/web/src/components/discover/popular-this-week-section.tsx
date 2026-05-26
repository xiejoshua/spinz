"use client";

import { AlbumCard } from "@/components/discover/album-card";
import { SectionShell } from "@/components/discover/section-shell";
import { useCoverFilter } from "@/components/discover/use-cover-filter";
import { apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type { PopularThisWeekResponse } from "@/lib/social-types";
import { useQuery } from "@tanstack/react-query";

const KEY = ["discover", "popular-this-week"] as const;

const SECTION_SIZE = 6;

export function PopularThisWeekSection() {
  const query = useQuery({
    queryKey: KEY,
    queryFn: async () =>
      apiClient.get<PopularThisWeekResponse>(
        `/api/v1/discover/popular-this-week?limit=${SECTION_SIZE}`
      ),
    staleTime: 5 * 60 * 1000,
  });

  // Hooks must run in the same order every render — pull useCoverFilter
  // out *before* any early returns so the isLoading branch doesn't shift
  // the hook count. (Was triggering "Rendered fewer hooks than expected"
  // crashing /discover?mode=albums when the query resolved.)
  const albums = query.data?.albums ?? [];
  const { visible, onCoverFailed } = useCoverFilter(albums, (a) => a.id);

  if (query.isLoading) {
    return (
      <SectionShell eyebrow="This week" headline="Popular albums">
        <SkeletonGrid />
      </SectionShell>
    );
  }

  if (visible.length === 0) {
    return null;
  }

  return (
    <SectionShell eyebrow="This week" headline="Popular albums">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {visible.map((album, index) => (
          <AlbumCard
            key={album.id}
            album={album}
            onCoverFailed={onCoverFailed}
            onClick={() => {
              capture("discover.popular.album_clicked", {
                album_id: album.id,
                position: index,
              });
            }}
          />
        ))}
      </div>
    </SectionShell>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6" aria-hidden="true">
      {Array.from({ length: SECTION_SIZE }, (_, i) => `skeleton-${i}`).map((id) => (
        <div key={id} className="flex flex-col gap-2">
          <div
            className="w-full rounded"
            style={{
              aspectRatio: "1 / 1",
              background: "var(--surface-secondary)",
              animation: "var(--skeleton-animation, shimmer) 1.6s infinite linear",
            }}
          />
          <div className="h-3 w-3/4 rounded" style={{ background: "var(--surface-secondary)" }} />
          <div className="h-3 w-1/2 rounded" style={{ background: "var(--surface-secondary)" }} />
        </div>
      ))}
    </div>
  );
}
