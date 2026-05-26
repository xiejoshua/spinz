"use client";

import { AlbumCard } from "@/components/discover/album-card";
import { SectionShell } from "@/components/discover/section-shell";
import { useCoverFilter } from "@/components/discover/use-cover-filter";
import { apiClient } from "@/lib/api-client";
import { capture } from "@/lib/posthog";
import type { FromFollowsResponse } from "@/lib/social-types";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

const KEY = ["discover", "from-follows"] as const;

const SECTION_SIZE = 6;

export function FromFollowsSection() {
  const query = useQuery({
    queryKey: KEY,
    queryFn: async () =>
      apiClient.get<FromFollowsResponse>(`/api/v1/discover/from-follows?limit=${SECTION_SIZE}`),
    staleTime: 60 * 1000,
  });

  // Hooks before any early return — see PopularThisWeekSection for the
  // rules-of-hooks rationale; same crash was tripping /discover?mode=albums.
  const items = query.data?.items ?? [];
  const idOf = useMemo(() => (item: { album: { id: string } }) => item.album.id, []);
  const { visible, onCoverFailed } = useCoverFilter(items, idOf);

  if (query.isLoading) {
    return (
      <SectionShell eyebrow="From your follows" headline="What they've been listening to">
        <SkeletonGrid />
      </SectionShell>
    );
  }
  if (visible.length === 0) {
    return (
      <SectionShell eyebrow="From your follows" headline="What they've been listening to">
        <p
          className="font-sans text-[14px] leading-[1.6]"
          style={{ color: "var(--muted)", maxWidth: "60ch" }}
        >
          Follow some critics to see what they're listening to.
        </p>
      </SectionShell>
    );
  }

  return (
    <SectionShell eyebrow="From your follows" headline="What they've been listening to">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {visible.map((item, index) => (
          <AlbumCard
            key={`${item.album.id}-${item.annotation.actor_handle}`}
            album={item.album}
            annotation={item.annotation}
            onCoverFailed={onCoverFailed}
            onClick={() => {
              capture("discover.from_follows.album_clicked", {
                album_id: item.album.id,
                position: index,
                follow_handle: item.annotation.actor_handle,
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
            }}
          />
          <div className="h-3 w-3/4 rounded" style={{ background: "var(--surface-secondary)" }} />
          <div className="h-3 w-1/2 rounded" style={{ background: "var(--surface-secondary)" }} />
        </div>
      ))}
    </div>
  );
}
