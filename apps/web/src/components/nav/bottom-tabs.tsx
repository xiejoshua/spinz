"use client";

import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";
import { Bookmark, Compass, Home, Plus, User } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType, SVGProps } from "react";

type TabDef = {
  href: string;
  label: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  match: (pathname: string) => boolean;
};

/**
 * Editorial bottom toolbar. Five slots — center is the LOG action
 * (the wedge) rendered as a peak/notch button in --accent burgundy.
 * Side tabs sit on hairline-divided cells with small-caps labels.
 */
export function BottomTabs() {
  const pathname = usePathname() ?? "/";
  const viewer = useAuthStore((s) => s.user);
  const openLogSheet = useUiStore((s) => s.openLogSheet);
  const profileHref = viewer?.handle ? `/profile/${viewer.handle}` : "/login";

  const leftTabs: TabDef[] = [
    {
      href: "/feed",
      label: "Home",
      Icon: Home,
      match: (p) => p === "/feed" || p === "/",
    },
    {
      href: "/up-next",
      label: "Up Next",
      Icon: Bookmark,
      match: (p) => p.startsWith("/up-next"),
    },
  ];
  const rightTabs: TabDef[] = [
    {
      href: "/discover",
      label: "Discover",
      Icon: Compass,
      match: (p) => p.startsWith("/discover"),
    },
    {
      href: profileHref,
      label: "Profile",
      Icon: User,
      match: (p) => p.startsWith("/profile"),
    },
  ];

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 backdrop-blur-md"
      style={{
        background: "color-mix(in oklab, var(--background) 88%, transparent)",
        borderTop: "1px solid var(--separator)",
      }}
    >
      <div className="mx-auto flex h-16 max-w-3xl items-stretch px-2">
        {leftTabs.map((t) => (
          <TabButton key={t.label} {...t} active={t.match(pathname)} />
        ))}
        <div className="relative flex items-center justify-center px-2">
          <button
            type="button"
            onClick={() => openLogSheet()}
            aria-label="Log an album"
            className="inline-flex h-14 w-14 -translate-y-3 cursor-pointer items-center justify-center rounded-full shadow-lg transition-transform focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--background)] active:scale-95"
            style={{
              background: "var(--accent)",
              color: "var(--accent-foreground)",
            }}
          >
            <Plus className="size-6" aria-hidden="true" strokeWidth={2.5} />
          </button>
        </div>
        {rightTabs.map((t) => (
          <TabButton key={t.label} {...t} active={t.match(pathname)} />
        ))}
      </div>
    </nav>
  );
}

function TabButton({ href, label, Icon, active }: TabDef & { active: boolean }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex flex-1 cursor-pointer flex-col items-center justify-center gap-1 transition-colors"
      )}
      style={{ color: active ? "var(--foreground)" : "var(--muted)" }}
    >
      <Icon className="size-5" aria-hidden="true" strokeWidth={active ? 2.25 : 1.75} />
      <span
        className="font-mono uppercase"
        style={{
          fontSize: "10px",
          letterSpacing: "0.12em",
          fontWeight: active ? 600 : 500,
        }}
      >
        {label}
      </span>
    </Link>
  );
}
