import { AccountSettings } from "@/components/settings/account-settings";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Account — auxd",
  description: "Change your email, password, or sign out of all devices.",
};

export default function AccountSettingsPage() {
  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-lg font-medium">Account</h2>
        <p className="text-sm text-muted-foreground">
          Change your email, password, or sign out everywhere.
        </p>
      </header>
      <AccountSettings />
    </section>
  );
}
