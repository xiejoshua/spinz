"use client";

import { ProfileShell } from "@/components/diary/profile-shell";
import { ProfileSettings } from "@/components/profile-settings";

type Props = {
  handle: string;
};

/** /profile/[handle]/settings body — settings UI inside ProfileShell. */
export function ProfileSettingsShell({ handle }: Props) {
  return (
    <ProfileShell handle={handle} activeTab="settings">
      <ProfileSettings />
    </ProfileShell>
  );
}
