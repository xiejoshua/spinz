"use client";

import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import { Bookmark, Compass, Home, User } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType, SVGProps } from "react";

type TabDef = {
  href: string;
  label: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  match: (pathname: string) => boolean;
};

export function BottomTabs() {
  const pathname = usePathname() ?? "/";
  const viewer = useAuthStore((s) => s.user);
  const profileHref = viewer?.handle ? `/profile/${viewer.handle}` : "/login";

  const tabs: TabDef[] = [
    { href: "/", label: "Home", Icon: Home, match: (p) => p === "/" },
    { href: "/up-next", label: "Up Next", Icon: Bookmark, match: (p) => p.startsWith("/up-next") },
    {
      href: "/discover",
      label: "Discover",
      Icon: Compass,
      match: (p) => p.startsWith("/discover"),
    },
    { href: profileHref, label: "Profile", Icon: User, match: (p) => p.startsWith("/profile") },
  ];

  return (
    <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-30 border-t bg-background">
      <ul className="container flex max-w-3xl items-stretch justify-around">
        {tabs.map(({ href, label, Icon, match }) => {
          const active = match(pathname);
          return (
            <li key={label} className="flex-1">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-16 flex-col items-center justify-center gap-1 text-xs",
                  active ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="size-5" aria-hidden="true" />
                <span>{label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
