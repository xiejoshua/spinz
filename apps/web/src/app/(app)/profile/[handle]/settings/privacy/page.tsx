import { ProfileSettingsSection } from "@/components/profile-settings/profile-settings-section";
import { PrivacySettingsForm } from "@/components/settings/privacy-settings-form";
import { FollowRequestsInbox } from "@/components/social/follow-requests";
import type { Metadata } from "next";

type Params = Promise<{ handle: string }>;

export const metadata: Metadata = {
  title: "Privacy — auxd",
  description: "Control who can see your activity on auxd.",
};

export default async function PrivacySettingsPage({ params }: { params: Params }) {
  const { handle } = await params;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  return (
    <article className="container max-w-3xl py-10">
      <ProfileSettingsSection
        handle={cleaned}
        label="Privacy"
        title="Who can see what."
        description="Default visibility for new entries, private-profile toggle, and pending follow requests."
      >
        <div className="space-y-10">
          <PrivacySettingsForm />
          <FollowRequestsInbox />
        </div>
      </ProfileSettingsSection>
    </article>
  );
}
