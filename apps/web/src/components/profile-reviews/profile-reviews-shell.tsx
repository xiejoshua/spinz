"use client";

import { ProfileShell } from "@/components/diary/profile-shell";
import { ProfileReviewsList } from "@/components/profile-reviews/profile-reviews-list";

type Props = {
  handle: string;
};

/** /profile/[handle]/reviews body — reviews list inside ProfileShell. */
export function ProfileReviewsShell({ handle }: Props) {
  return (
    <ProfileShell handle={handle} activeTab="reviews">
      <ProfileReviewsList handle={handle} />
    </ProfileShell>
  );
}
