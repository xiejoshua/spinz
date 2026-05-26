"use client";

import { DiscoverSearchBar } from "@/components/discover/discover-search-bar";
import { FromFollowsSection } from "@/components/discover/from-follows-section";
import { PopularThisWeekSection } from "@/components/discover/popular-this-week-section";
import { SectionShell } from "@/components/discover/section-shell";
import { SuggestionsList } from "@/components/discover/suggestions-list";
import { capture } from "@/lib/posthog";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo } from "react";

type Mode = "people" | "albums";
const VALID_MODES: Mode[] = ["people", "albums"];

/**
 * Editorial Discover homepage (003 / Option A — iteration 1).
 *
 * Mode-conditional layout:
 *
 * * **People** tab → ``<SuggestionsList>`` ("People worth your taste").
 * * **Albums** tab → inline "advanced search" hint + Popular This Week
 *   + From Your Follows.
 *
 * Mode is owned by the URL (``?mode=people|albums``) so both this
 * shell and ``<DiscoverSearchBar>`` read from the same source; the
 * search bar also writes to the URL when toggled.
 *
 * Legacy compatibility: ``?tab=albums`` redirects to ``/search``;
 * ``?tab=people`` collapses to the default surface.
 */
export function DiscoverFrontPage() {
  const router = useRouter();
  const pathname = usePathname() ?? "/discover";
  const searchParams = useSearchParams();

  const mode: Mode = useMemo(() => {
    const raw = searchParams?.get("mode");
    return (VALID_MODES as string[]).includes(raw ?? "") ? ((raw as Mode) ?? "people") : "people";
  }, [searchParams]);

  useEffect(() => {
    const tab = searchParams?.get("tab");
    if (tab === "albums") {
      router.replace("/search", { scroll: false });
    } else if (tab === "people") {
      const params = new URLSearchParams(searchParams?.toString() ?? "");
      params.delete("tab");
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    }
  }, [pathname, router, searchParams]);

  return (
    <div className="space-y-12">
      <div className="space-y-3">
        <DiscoverSearchBar />
        {mode === "albums" && <AdvancedSearchHint />}
      </div>
      {mode === "people" ? (
        <SectionShell eyebrow="People worth your taste" headline="Critics to follow">
          <SuggestionsList />
        </SectionShell>
      ) : (
        <>
          <PopularThisWeekSection />
          <FromFollowsSection />
        </>
      )}
    </div>
  );
}

function AdvancedSearchHint() {
  return (
    <p className="font-sans text-[13px] leading-[1.55]" style={{ color: "var(--muted)" }}>
      Looking for something specific?{" "}
      <Link
        href="/search"
        onClick={() => {
          capture("discover.cta.advanced_search", { source: "albums_hint" });
        }}
        className="font-medium underline"
        style={{ color: "var(--accent)" }}
      >
        Open advanced search →
      </Link>
    </p>
  );
}
