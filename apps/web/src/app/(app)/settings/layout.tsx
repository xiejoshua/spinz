import { PageHeader } from "@/components/nav/page-header";
import { SettingsNav } from "@/components/settings/settings-nav";
import type { ReactNode } from "react";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <article className="container max-w-3xl space-y-8 py-10">
      <PageHeader
        eyebrow="Account"
        title="Settings."
        subtitle="Manage your account, profile, privacy, and data."
      />
      <SettingsNav />
      <div>{children}</div>
    </article>
  );
}
