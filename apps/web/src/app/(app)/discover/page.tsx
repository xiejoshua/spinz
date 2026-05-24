import { DiscoverTabs } from "@/components/discover/discover-tabs";
import { PageHeader } from "@/components/nav/page-header";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Discover — auxd",
  description:
    "Find people whose taste you trust, and browse the catalog for albums to log.",
};

export default function DiscoverPage() {
  return (
    <article className="container max-w-3xl space-y-8 py-10">
      <PageHeader
        eyebrow="Discover"
        title="What's good."
        subtitle="People worth following, and albums worth opening — both in one place."
      />
      <DiscoverTabs />
    </article>
  );
}
