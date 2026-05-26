import { DiscoverFrontPage } from "@/components/discover/discover-front-page";
import { PageHeader } from "@/components/nav/page-header";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Discover — auxd",
  description:
    "Find people worth following, albums popular this week, and what your follows are listening to — all on one editorial page.",
};

export default function DiscoverPage() {
  return (
    <article className="container max-w-5xl space-y-10 py-10">
      <PageHeader
        eyebrow="Discover"
        title="What's good."
        subtitle="Find people. Find albums. One newspaper, two columns."
      />
      <DiscoverFrontPage />
    </article>
  );
}
