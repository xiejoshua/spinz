"use client";

import { DiaryList } from "@/components/diary/diary-list";
import { ProfileShell } from "@/components/diary/profile-shell";
import { useAuthStore } from "@/stores/auth";

type Props = {
  handle: string;
};

/**
 * /profile/[handle] body — wraps the diary list in the shared
 * editorial ProfileShell.
 */
export function ProfileClient({ handle }: Props) {
  const viewer = useAuthStore((s) => s.user);
  const isOwner = viewer?.handle === handle;
  return (
    <ProfileShell handle={handle} activeTab="diary">
      <DiaryList handle={handle} isOwner={isOwner} />
    </ProfileShell>
  );
}
