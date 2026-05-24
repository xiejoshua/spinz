import { SuggestionsList } from "@/components/discover/suggestions-list";
import { PageHeader } from "@/components/nav/page-header";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Discover — auxd",
  description: "Suggested people to follow based on your listening taste.",
};

export default function DiscoverPage() {
  return (
    <article className="container max-w-3xl space-y-8 py-10">
      <PageHeader
        eyebrow="Discover"
        title="People to follow."
        subtitle="Suggestions from mutual taste, your follow graph, and shared critics."
      />
      <SuggestionsList />
    </article>
  );
}
