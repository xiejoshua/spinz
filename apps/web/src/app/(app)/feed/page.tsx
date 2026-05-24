import { FeedList } from "@/components/feed/feed-list";
import { PageHeader } from "@/components/nav/page-header";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Home — auxd",
  description: "Your friends and critics' recent diary entries on auxd.",
};

export default function HomePage() {
  return (
    <article className="container max-w-3xl space-y-8 py-10">
      <PageHeader eyebrow="Feed" title="Home." />
      <FeedList />
    </article>
  );
}
