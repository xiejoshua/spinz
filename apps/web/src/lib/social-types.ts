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
