export type DiaryVisibility = "public" | "followers" | "private";

export type DiaryEntry = {
  id: string;
  user_id: string;
  album_id: string;
  logged_at: string;
  rating: number | null;
  auxed: boolean;
  review_id: string | null;
  visibility: DiaryVisibility;
  relisten: boolean;
  edited_at: string | null;
  created_at: string;
  deleted_at: string | null;
};

export type DiaryAlbumCard = {
  id: string;
  mbid: string | null;
  title: string;
  artist_credit: string;
  release_year: number | null;
  cover_art_url: string | null;
};

export type DiaryListResponse = {
  entries: DiaryEntry[];
  next_cursor: string | null;
  albums: Record<string, DiaryAlbumCard>;
};
