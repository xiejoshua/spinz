import { FeedList } from "@/components/feed/feed-list";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Home — auxd",
  description: "Your friends and critics' recent diary entries on auxd.",
};

export default function HomePage() {
  return (
    <article className="container max-w-3xl space-y-4 py-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Home</h1>
      </header>
      <FeedList />
    </article>
  );
}
