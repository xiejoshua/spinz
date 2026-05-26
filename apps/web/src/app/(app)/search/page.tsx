import { PageHeader } from "@/components/nav/page-header";
import { AdvancedSearchClient } from "@/components/search/advanced-search-client";
import { ChevronLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Search — auxd",
  description:
    "Search the auxd catalog by query, decade, year range, genre, and sort. Filters mirror to the URL — every search is shareable.",
};

export default function SearchPage() {
  return (
    <article className="container max-w-5xl space-y-8 py-10">
      <Link
        href="/discover"
        className="search-back-link inline-flex items-center gap-1 font-sans text-[13px] font-medium transition-colors"
        style={{ color: "var(--muted)" }}
      >
        <ChevronLeft aria-hidden="true" className="size-4" />
        Back to Discover
      </Link>
      <PageHeader
        eyebrow="Search"
        title="Browse the catalog."
        subtitle="Filter by decade, year, genre, or sort to dig past the simple lookup."
      />
      <AdvancedSearchClient />
      <style>{`
        .search-back-link:hover { color: var(--accent); }
        .search-back-link:focus-visible {
          outline: 2px solid var(--focus);
          outline-offset: 2px;
          border-radius: 2px;
        }
      `}</style>
    </article>
  );
}
