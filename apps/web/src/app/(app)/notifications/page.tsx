import { NotificationList } from "@/components/notifications/notification-list";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Notifications — auxd",
  description: "Recent activity from people you follow on auxd.",
};

export default function NotificationsPage() {
  return (
    <article className="container max-w-3xl space-y-4 py-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Notifications</h1>
        <p className="text-sm text-muted-foreground">
          Updates from people you follow and account events.
        </p>
      </header>
      <NotificationList />
    </article>
  );
}
