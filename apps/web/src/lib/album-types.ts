export type Track = {
  position: number;
  title: string;
  duration_ms: number | null;
  artist_credit?: string | null;
};

export type AlbumPayload = {
  id: string;
  mbid: string | null;
  discogs_release_id: string | null;
  title: string;
  artist_credit: string;
  release_year: number | null;
  cover_art_url: string | null;
  label: string | null;
  genres: string[];
  tracklist: Track[];
  duration_ms: number | null;
  source: string;
};

export type AlbumAggregate = {
  avg_rating: number;
  rating_count: number;
  review_count: number;
  aux_count: number;
  like_count: number;
};

export type DiaryRow = {
  id: string;
  user_id: string;
  logged_at: string;
  rating: number | null;
  auxed: boolean;
  review_id: string | null;
  visibility: string;
};

export type ReviewRow = {
  id: string;
  user_id: string;
  diary_entry_id: string;
  body: string;
  likes_count: number;
  visibility: string;
  created_at: string;
};

export type AlbumDetailResponse = {
  album: AlbumPayload;
  editions: AlbumPayload[];
  aggregate: AlbumAggregate;
  my_history: DiaryRow[];
  friends: DiaryRow[];
  public_reviews: ReviewRow[];
};
