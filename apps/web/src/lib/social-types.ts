import type { ReviewUserCard } from "@/lib/review-types";

export type FollowState = "none" | "following" | "pending" | "self" | "blocked" | "anonymous";

export type ProfileResponse = {
  user: ReviewUserCard & { bio: string | null; private_profile: boolean };
  counts: { followers: number; following: number };
  relation: FollowState;
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
