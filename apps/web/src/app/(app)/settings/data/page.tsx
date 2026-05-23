import { DataSettings } from "@/components/settings/data-settings";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Data — auxd",
  description: "Export your data or delete your account.",
};

export default function DataSettingsPage() {
  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-lg font-medium">Data</h2>
        <p className="text-sm text-muted-foreground">
          Export everything we know about you, or close your account.
        </p>
      </header>
      <DataSettings />
    </section>
  );
}
