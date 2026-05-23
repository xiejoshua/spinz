"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type FeedSort = "newest" | "most_liked" | "highest_rated";

export type LogSheetVisibility = "public" | "followers" | "private";

export type LogSheetEdit = {
  entry_id: string;
  rating: number | null;
  auxed: boolean;
  visibility: LogSheetVisibility;
};

export type LogSheetSeed = {
  album_id: string;
  mbid: string | null;
  title: string;
  artist_credit: string;
  cover_art_url: string | null;
  /** When set, the sheet opens in edit mode and PATCHes the existing entry. */
  edit?: LogSheetEdit;
};

type UiState = {
  logSheetOpen: boolean;
  logSheetSeed: LogSheetSeed | null;
  feedSort: FeedSort;
  openLogSheet: (seed?: LogSheetSeed) => void;
  closeLogSheet: () => void;
  toggleLogSheet: () => void;
  setFeedSort: (sort: FeedSort) => void;
};

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      logSheetOpen: false,
      logSheetSeed: null,
      feedSort: "newest",
      openLogSheet: (seed) => set({ logSheetOpen: true, logSheetSeed: seed ?? null }),
      closeLogSheet: () => set({ logSheetOpen: false, logSheetSeed: null }),
      toggleLogSheet: () =>
        set((s) => ({
          logSheetOpen: !s.logSheetOpen,
          logSheetSeed: s.logSheetOpen ? null : s.logSheetSeed,
        })),
      setFeedSort: (feedSort) => set({ feedSort }),
    }),
    {
      name: "auxd-ui",
      partialize: (state) => ({ feedSort: state.feedSort }),
    }
  )
);
