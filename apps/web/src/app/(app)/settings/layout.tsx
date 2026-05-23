import { SettingsNav } from "@/components/settings/settings-nav";
import type { ReactNode } from "react";

export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <article className="container max-w-3xl space-y-6 py-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account, profile, privacy, and data.
        </p>
      </header>
      <SettingsNav />
      <div>{children}</div>
    </article>
  );
}
