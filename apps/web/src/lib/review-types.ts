export type ReviewVisibility = "public" | "followers" | "private";

export type Review = {
  id: string;
  user_id: string;
  diary_entry_id: string;
  album_id: string;
  body: string;
  visibility: ReviewVisibility;
  likes_count: number;
  recent_likers: string[];
  edited_at: string | null;
  deleted_at: string | null;
  created_at: string;
};

export type ReviewUserCard = {
  id: string;
  handle: string;
  display_name: string;
  avatar_url: string | null;
};

export type ReviewSort = "newest" | "most_liked" | "highest_rated";

export type ReviewsListResponse = {
  reviews: Review[];
  next_cursor: string | null;
  users: Record<string, ReviewUserCard>;
};

/** Minimal album-card payload joined into the user-reviews sidecar (T094). */
export type ReviewAlbumCard = {
  id: string;
  mbid: string | null;
  title: string;
  artist_credit: string;
  release_year: number | null;
  cover_art_url: string | null;
};

/** Response shape for ``GET /api/v1/users/{handle}/reviews`` (T094). */
export type UserReviewsListResponse = {
  reviews: Review[];
  next_cursor: string | null;
  users: Record<string, ReviewUserCard>;
  albums: Record<string, ReviewAlbumCard>;
};

export type ReviewLikeResponse = {
  liked: boolean;
  likes_count: number;
};
