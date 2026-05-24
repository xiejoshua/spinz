import { DataSettings } from "@/components/settings/data-settings";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data — auxd",
  description: "Export your data or delete your account.",
};

export default function DataSettingsPage() {
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
          Data
        </h2>
        <p className="font-sans text-[14px]" style={{ color: "var(--muted)" }}>
          Export everything we know about you, or close your account.
        </p>
      </header>
      <DataSettings />
    </section>
  );
}
