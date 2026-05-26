"use client";

import { useCallback, useMemo, useState } from "react";

/**
 * Tracks albums whose cover-art request 404'd at runtime so each
 * Discover surface can drop them from its grid.
 *
 * The backend ``require_cover`` filter only catches the "definitely
 * no art" case (no mbid AND no cover_art_url). Albums whose ``mbid``
 * routes through the cover proxy but where coverartarchive.org
 * doesn't actually host the image — and the ``cover_art_url``
 * fallback is itself missing or also 404s — slip past that filter
 * and render as broken cells. This hook lets each consumer collect
 * those at the ``<img onError>`` callback and filter them out of
 * subsequent renders.
 *
 * Returns a (results, onCoverFailed) pair: pass the callback into
 * each ``<AlbumCard>``, render the filtered list. Failed IDs are
 * accumulated across all pages so a card removed on page 1 stays
 * removed when load-more arrives.
 */
export function useCoverFilter<T>(
  items: T[],
  idOf: (item: T) => string
): {
  visible: T[];
  onCoverFailed: (albumId: string) => void;
} {
  const [failedIds, setFailedIds] = useState<Set<string>>(() => new Set());

  const onCoverFailed = useCallback((albumId: string) => {
    setFailedIds((prev) => {
      if (prev.has(albumId)) return prev;
      const next = new Set(prev);
      next.add(albumId);
      return next;
    });
  }, []);

  const visible = useMemo(() => {
    if (failedIds.size === 0) return items;
    return items.filter((item) => !failedIds.has(idOf(item)));
  }, [items, failedIds, idOf]);

  return { visible, onCoverFailed };
}
