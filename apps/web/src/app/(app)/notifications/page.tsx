import { PageHeader } from "@/components/nav/page-header";
import { NotificationList } from "@/components/notifications/notification-list";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Notifications — auxd",
  description: "Recent activity from people you follow on auxd.",
};

export default function NotificationsPage() {
  return (
    <article className="container max-w-3xl space-y-8 py-10">
      <PageHeader
        eyebrow="Activity"
        title="Notifications."
        subtitle="Updates from people you follow and account events."
      />
      <NotificationList />
    </article>
  );
}
