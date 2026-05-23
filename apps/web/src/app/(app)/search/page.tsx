import { SearchClient } from "@/components/search/search-client";

export default function SearchPage() {
  return (
    <section className="container max-w-3xl py-6 space-y-4">
      <h1 className="text-2xl font-bold tracking-tight">Search</h1>
      <SearchClient />
    </section>
  );
}
