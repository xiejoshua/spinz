import { NotificationPrefsForm } from "@/components/notifications/prefs-form";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Notification preferences — auxd",
  description: "Manage which auxd notifications reach you and where.",
};

export default function NotificationPreferencesPage() {
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
          Notifications
        </h2>
        <p className="font-sans text-[14px]" style={{ color: "var(--muted)" }}>
          Choose what auxd should tell you about, and on which channels.
        </p>
      </header>
      <NotificationPrefsForm />
    </section>
  );
}
