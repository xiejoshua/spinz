import { ProfileSettingsSection } from "@/components/profile-settings/profile-settings-section";
import { DataSettings } from "@/components/settings/data-settings";
import type { Metadata } from "next";

type Params = Promise<{ handle: string }>;

export const metadata: Metadata = {
  title: "Data — auxd",
  description: "Export your data or delete your account.",
};

export default async function DataSettingsPage({ params }: { params: Params }) {
  const { handle } = await params;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  return (
    <article className="container max-w-3xl py-10">
      <ProfileSettingsSection
        handle={cleaned}
        label="Data"
        title="Export or close."
        description="Download everything we know about you, or schedule your account for deletion."
      >
        <DataSettings />
      </ProfileSettingsSection>
    </article>
  );
}
