import { EditProfileForm } from "@/components/settings/edit-profile-form";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Edit profile — auxd",
  description: "Update your display name, bio, handle, and avatar.",
};

export default function ProfileSettingsPage() {
  return (
    <section className="space-y-4">
      <header className="space-y-2">
        <h2
          className="font-serif font-semibold tracking-[-0.01em]"
          style={{
            fontSize: "22px",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          Profile
        </h2>
        <p className="font-sans text-[14px]" style={{ color: "var(--muted)" }}>
          Update how your profile appears across auxd.
        </p>
      </header>
      <EditProfileForm />
    </section>
  );
}
