import { ProfileSettingsShell } from "@/components/profile-settings/profile-settings-shell";
import type { Metadata } from "next";

type Params = Promise<{ handle: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { handle } = await params;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  return {
    title: `Settings — @${cleaned} — auxd`,
    description: `Settings for ${cleaned} on auxd`,
  };
}

/**
 * Profile settings tab (T145+). Surfaces avatar upload, display
 * name / bio, handle change, email change, and password change in
 * one editorial sheet — the four user-spec items for self-service
 * account control. ProfileShell handles the "not your settings"
 * gate when a non-owner navigates here directly.
 */
export default async function ProfileSettingsPage({ params }: { params: Params }) {
  const { handle } = await params;
  const cleaned = handle.startsWith("@") ? handle.slice(1) : handle;
  return (
    <article className="container max-w-3xl py-10">
      <ProfileSettingsShell handle={cleaned} />
    </article>
  );
}
