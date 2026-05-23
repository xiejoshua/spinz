import type { DiaryAlbumCard } from "@/lib/diary-types";
import type { ReviewUserCard } from "@/lib/review-types";

export type FeedMode = "for_you" | "latest";

export type FeedEntry = {
  kind: "diary_entry" | "review";
  id: string;
  user_id: string;
  album_id: string;
  logged_at: string;
  rating: number | null;
  auxed: boolean;
  review_id: string | null;
  score?: number;
  score_components?: Record<string, unknown>;
};

export type FeedReviewSnippet = {
  id: string;
  body_preview: string;
  likes_count: number;
};

export type FeedListResponse = {
  entries: FeedEntry[];
  next_cursor: string | null;
  users: Record<string, ReviewUserCard>;
  albums: Record<string, DiaryAlbumCard>;
  reviews: Record<string, FeedReviewSnippet>;
  mode: FeedMode;
};
