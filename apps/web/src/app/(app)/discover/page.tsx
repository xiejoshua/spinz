import { SuggestionsList } from "@/components/discover/suggestions-list";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Discover — auxd",
  description: "Suggested people to follow based on your listening taste.",
};

export default function DiscoverPage() {
  return (
    <article className="container max-w-3xl space-y-4 py-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Discover</h1>
        <p className="text-sm text-muted-foreground">
          People you might like — based on mutual taste, your follow graph, and shared critics.
        </p>
      </header>
      <SuggestionsList />
    </article>
  );
}
