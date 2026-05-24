"use client";

import { DiaryList } from "@/components/diary/diary-list";
import { ProfileShell } from "@/components/diary/profile-shell";
import { ProfileReviewsList } from "@/components/profile-reviews/profile-reviews-list";
import { useAuthStore } from "@/stores/auth";

export type ProfileView = "diary" | "reviews";

type Props = {
  handle: string;
  view: ProfileView;
};

/**
 * /profile/[handle] body — wraps the diary or reviews list in the
 * shared editorial ProfileShell. ``view`` is driven by the
 * ``?view=reviews`` search param on the page route so the Reviews
 * tab in ProfileShell stays deep-linkable without spawning a
 * dedicated sub-route.
 */
export function ProfileClient({ handle, view }: Props) {
  const viewer = useAuthStore((s) => s.user);
  const isOwner = viewer?.handle === handle;
  return (
    <ProfileShell handle={handle} activeTab={view}>
      {view === "reviews" ? (
        <ProfileReviewsList handle={handle} />
      ) : (
        <DiaryList handle={handle} isOwner={isOwner} />
      )}
    </ProfileShell>
  );
}
