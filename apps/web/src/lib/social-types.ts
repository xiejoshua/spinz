import type { ReviewUserCard } from "@/lib/review-types";

export type FollowState = "none" | "following" | "pending" | "self" | "blocked" | "anonymous";

export type ProfileResponse = {
  user: ReviewUserCard & {
    bio: string | null;
    private_profile: boolean;
    is_critic_seed?: boolean;
  };
  counts: { followers: number; following: number };
  relation: FollowState;
};

export type FollowRequestEntry = {
  id: string;
  requester_id: string;
  created_at: string;
};

export type FollowRequestsListResponse = {
  requests: FollowRequestEntry[];
  users: Record<string, ReviewUserCard>;
  next_cursor: string | null;
};

export type FollowMutationResponse = {
  state: "accepted" | "pending";
  follow_id: string;
  followee_id: string;
};

export type SuggestionEntry = {
  user: ReviewUserCard;
  score: number;
  reasons: string[];
  computed_at: string;
};

export type SuggestionsResponse = {
  suggestions: SuggestionEntry[];
};

export type OnboardingCardUser = {
  id: string;
  handle: string;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
};

export type OnboardingCard = {
  user: OnboardingCardUser;
  pre_checked: boolean;
  source: "onboarding_preselected" | "onboarding_mutual_taste";
  score: number;
  genre_signature: string[];
};

export type OnboardingCardsResponse = {
  cards: OnboardingCard[];
};

// ---------------------------------------------------------------------------
// Discover-rehaul (003)
// ---------------------------------------------------------------------------

export type UserSearchResult = {
  id: string;
  handle: string;
  display_name: string;
  avatar_url: string | null;
};

export type UserSearchResponse = {
  results: UserSearchResult[];
};

export type DiscoverAlbumSummary = {
  id: string;
  mbid: string | null;
  discogs_release_id: string | null;
  title: string;
  artist_name: string;
  release_year: number | null;
  cover_art_url: string | null;
  /** Provider-supplied genre tags (003 iteration — feeds the advanced-search filter). */
  genres?: string[];
};

export type PopularAlbumItem = DiscoverAlbumSummary & {
  log_count: number;
};

export type PopularThisWeekResponse = {
  albums: PopularAlbumItem[];
};

export type FromFollowsAnnotation = {
  actor_handle: string;
  actor_display_name: string;
  actor_avatar_url: string | null;
  verb: "rated" | "reviewed" | "logged";
  rating: number | null;
  logged_at: string;
};

export type FromFollowsItem = {
  album: DiscoverAlbumSummary;
  annotation: FromFollowsAnnotation;
};

export type FromFollowsResponse = {
  items: FromFollowsItem[];
};
