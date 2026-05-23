import { NotificationPrefsForm } from "@/components/notifications/prefs-form";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Notification preferences — auxd",
  description: "Manage which auxd notifications reach you and where.",
};

export default function NotificationPreferencesPage() {
  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-lg font-medium">Notifications</h2>
        <p className="text-sm text-muted-foreground">
          Choose what auxd should tell you about, and on which channels.
        </p>
      </header>
      <NotificationPrefsForm />
    </section>
  );
}
