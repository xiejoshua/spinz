import { EditProfileForm } from "@/components/settings/edit-profile-form";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Edit profile — auxd",
  description: "Update your display name, bio, handle, and avatar.",
};

export default function ProfileSettingsPage() {
  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-lg font-medium">Profile</h2>
        <p className="text-sm text-muted-foreground">
          Update how your profile appears across auxd.
        </p>
      </header>
      <EditProfileForm />
    </section>
  );
}
