import { PrivacySettingsForm } from "@/components/settings/privacy-settings-form";
import { FollowRequestsInbox } from "@/components/social/follow-requests";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy — auxd",
  description: "Control who can see your activity on auxd.",
};

export default function PrivacySettingsPage() {
  return (
    <section className="space-y-8">
      <div className="space-y-1">
        <h2 className="text-lg font-medium">Privacy</h2>
        <p className="text-sm text-muted-foreground">
          Control who can see your diary, reviews, lists, and Up Next backlog.
        </p>
      </div>
      <PrivacySettingsForm />
      <FollowRequestsInbox />
    </section>
  );
}
