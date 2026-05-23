"use client";

import type { LogSheetSeed } from "@/stores/ui";
import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "auxd-log-recent-searches";
const MAX_RECENT = 5;

export type RecentSearch = LogSheetSeed & { query: string; title: string; artist_name: string };

function loadRecent(): RecentSearch[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as RecentSearch[]) : [];
  } catch {
    return [];
  }
}

function saveRecent(value: RecentSearch[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // localStorage may be unavailable (Safari private mode, quota); swallow.
  }
}

export function useRecentLogSearches() {
  const [recent, setRecent] = useState<RecentSearch[]>([]);

  useEffect(() => {
    setRecent(loadRecent());
  }, []);

  const push = useCallback((entry: RecentSearch) => {
    setRecent((current) => {
      const without = current.filter((r) => r.album_id !== entry.album_id);
      const next = [entry, ...without].slice(0, MAX_RECENT);
      saveRecent(next);
      return next;
    });
  }, []);

  return { recent, push };
}
