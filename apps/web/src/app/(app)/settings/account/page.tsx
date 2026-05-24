import { AccountSettings } from "@/components/settings/account-settings";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Account — auxd",
  description: "Change your email, password, or sign out of all devices.",
};

export default function AccountSettingsPage() {
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
          Account
        </h2>
        <p className="font-sans text-[14px]" style={{ color: "var(--muted)" }}>
          Change your email, password, or sign out everywhere.
        </p>
      </header>
      <AccountSettings />
    </section>
  );
}
