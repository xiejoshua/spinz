import type { DiaryAlbumCard } from "@/lib/diary-types";

export type BacklogVisibility = "public" | "followers" | "private" | null;

export type BacklogItem = {
  id: string;
  backlog_id: string;
  album_id: string;
  position: number;
  per_item_visibility: BacklogVisibility;
  notes: string | null;
  added_at: string;
};

export type BacklogListResponse = {
  items: BacklogItem[];
  next_cursor: string | null;
  albums: Record<string, DiaryAlbumCard>;
};

export type BacklogContainsResponse = {
  in_backlog: boolean;
  item_id: string | null;
};
