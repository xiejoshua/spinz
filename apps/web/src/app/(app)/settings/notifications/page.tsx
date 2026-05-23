import { NotificationPrefsForm } from "@/components/notifications/prefs-form";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Notification preferences — auxd",
  description: "Manage which auxd notifications reach you and where.",
};

export default function NotificationPreferencesPage() {
  return (
    <article className="container max-w-3xl space-y-4 py-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Notifications</h1>
        <p className="text-sm text-muted-foreground">
          Choose what auxd should tell you about, and on which channels.
        </p>
      </header>
      <NotificationPrefsForm />
    </article>
  );
}
