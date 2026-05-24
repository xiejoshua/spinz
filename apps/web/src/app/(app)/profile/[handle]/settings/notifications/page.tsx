import { NotificationPrefsForm } from "@/components/notifications/prefs-form";
import { ProfileSettingsSection } from "@/components/profile-settings/profile-settings-section";
import type { Metadata } from "next";

type Params = Promise<{ handle: string }>;

export const metadata: Metadata = {
  title: "Notification preferences — auxd",
  description: "Manage which auxd notifications reach you and where.",
};

export default async function NotificationSettingsPage({ params }: { params: Params }) {
  const { handle } = await params;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  return (
    <article className="container max-w-3xl py-10">
      <ProfileSettingsSection
        handle={cleaned}
        label="Notifications"
        title="What we'll tell you."
        description="Per-channel toggles for each notification type. Locked rows (security emails) can't be turned off."
      >
        <NotificationPrefsForm />
      </ProfileSettingsSection>
    </article>
  );
}
