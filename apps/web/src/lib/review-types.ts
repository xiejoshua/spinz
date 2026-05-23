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

export type ReviewLikeResponse = {
  liked: boolean;
  likes_count: number;
};
