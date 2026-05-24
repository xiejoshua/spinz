import { PageHeader } from "@/components/nav/page-header";
import { SearchClient } from "@/components/search/search-client";

export default function SearchPage() {
  return (
    <section className="container max-w-3xl space-y-8 py-10">
      <PageHeader eyebrow="Catalog" title="Search." />
      <SearchClient />
    </section>
  );
}
