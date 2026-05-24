"use client";

import { SearchClient } from "@/components/search/search-client";
import { SuggestionsList } from "@/components/discover/suggestions-list";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

type DiscoverTab = "people" | "albums";

const VALID: DiscoverTab[] = ["people", "albums"];

const TAB_META: Record<DiscoverTab, { label: string; eyebrow: string }> = {
  people: { label: "People", eyebrow: "Who to follow" },
  albums: { label: "Albums", eyebrow: "Search the catalog" },
};

/**
 * Discover surface split into People (suggestions) + Albums (catalog
 * search). The active tab is mirrored on the URL via ?tab= so the
 * surface is sharable / bookmarkable / back-button-navigable.
 *
 * People → SuggestionsList (existing): suggested follows with reason
 * codes.
 * Albums → SearchClient (existing): debounced album search hitting
 * the same /api/v1/search endpoint that powers the Log sheet, just
 * surfaced as a browsing surface instead of a logging one.
 */
export function DiscoverTabs() {
  const router = useRouter();
  const pathname = usePathname() ?? "/discover";
  const searchParams = useSearchParams();
  const rawTab = searchParams?.get("tab") ?? "people";
  const tab: DiscoverTab = (VALID as string[]).includes(rawTab)
    ? (rawTab as DiscoverTab)
    : "people";

  const setTab = useCallback(
    (next: DiscoverTab) => {
      const params = new URLSearchParams(searchParams?.toString() ?? "");
      if (next === "people") {
        params.delete("tab");
      } else {
        params.set("tab", next);
      }
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams]
  );

  return (
    <div className="space-y-6">
      <TabBar value={tab} onChange={setTab} />
      <EyebrowLine text={TAB_META[tab].eyebrow} />
      <div>
        {tab === "people" && <SuggestionsList />}
        {tab === "albums" && <SearchClient />}
      </div>
    </div>
  );
}

function TabBar({
  value,
  onChange,
}: {
  value: DiscoverTab;
  onChange: (next: DiscoverTab) => void;
}) {
  const tabs = useMemo<DiscoverTab[]>(() => ["people", "albums"], []);
  return (
    <nav
      aria-label="Discover sections"
      className="flex gap-6"
      style={{ borderBottom: "1px solid var(--separator)" }}
    >
      {tabs.map((t) => {
        const active = t === value;
        return (
          <button
            key={t}
            type="button"
            onClick={() => onChange(t)}
            aria-current={active ? "page" : undefined}
            className="inline-block cursor-pointer px-1 py-3 font-sans text-[15px] font-medium"
            style={{
              color: active ? "var(--foreground)" : "var(--muted)",
              borderBottom: active
                ? "2px solid var(--foreground)"
                : "2px solid transparent",
              marginBottom: "-1px",
              background: "transparent",
            }}
          >
            {TAB_META[t].label}
          </button>
        );
      })}
    </nav>
  );
}

function EyebrowLine({ text }: { text: string }) {
  return (
    <div
      className="font-mono uppercase"
      style={{
        fontSize: "11px",
        letterSpacing: "0.18em",
        color: "var(--muted)",
      }}
    >
      {text}
    </div>
  );
}
