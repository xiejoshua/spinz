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
      <div className="space-y-2">
        <h2
          className="font-serif font-semibold tracking-[-0.01em]"
          style={{
            fontSize: "22px",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          Privacy
        </h2>
        <p className="font-sans text-[14px]" style={{ color: "var(--muted)" }}>
          Control who can see your diary, reviews, lists, and Up Next backlog.
        </p>
      </div>
      <PrivacySettingsForm />
      <FollowRequestsInbox />
    </section>
  );
}
