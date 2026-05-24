"use client";

import { Avatar } from "@heroui/react";
import { AuxIcon } from "@/components/icons/aux";
import { StarRow } from "@/components/icons/star-row";

type Entry = {
  user: { name: string; handle: string; initials: string };
  timeAgo: string;
  rating: number;
  auxed?: boolean;
  album: { title: string; artist: string; year: string };
  review?: string;
};

const ENTRIES: Entry[] = [
  {
    user: { name: "Marcus", handle: "marcus", initials: "MK" },
    timeAgo: "2h",
    rating: 5,
    auxed: true,
    album: {
      title: "The Predatory Wasp of the Palisades…",
      artist: "Sufjan Stevens",
      year: "2005",
    },
    review:
      "Comes back to me every spring. The horn section on the bridge is the most quietly devastating…",
  },
  {
    user: { name: "Hana", handle: "hana", initials: "HN" },
    timeAgo: "5h",
    rating: 4,
    album: {
      title: "Two Star & The Dream Police",
      artist: "Mk.gee",
      year: "2024",
    },
  },
  {
    user: { name: "Theo", handle: "theo", initials: "TM" },
    timeAgo: "8h",
    rating: 5,
    album: { title: "GNX", artist: "Kendrick Lamar", year: "2024" },
    review:
      "The case for GNX as a major work hinges on its refusal to do the work of legacy positioning…",
  },
];

export function ExampleFeed() {
  return (
    <section className="w-full" style={{ background: "var(--surface)" }}>
      <div className="mx-auto max-w-3xl px-6 py-24 sm:py-28">
        <div
          className="mb-2 font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          What your feed looks like
        </div>
        <div className="h-px" style={{ background: "var(--separator)" }} />

        <ul className="mt-8 space-y-10">
          {ENTRIES.map((e) => (
            <li key={e.user.handle}>
              <article className="flex gap-4">
                <Avatar size="md" className="shrink-0">
                  <Avatar.Fallback>{e.user.initials}</Avatar.Fallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <header
                    className="flex flex-wrap items-baseline gap-x-2 font-sans text-[14px]"
                    style={{ color: "var(--foreground)" }}
                  >
                    <span className="font-semibold">{e.user.name}</span>
                    <span
                      className="font-mono text-[12px]"
                      style={{ color: "var(--muted)" }}
                    >
                      @{e.user.handle}
                    </span>
                    <span
                      className="text-[12px]"
                      style={{ color: "var(--muted)" }}
                    >
                      · {e.timeAgo}
                    </span>
                  </header>

                  <div
                    className="mt-1 inline-flex items-center gap-2"
                    style={{ color: "var(--accent)" }}
                  >
                    <StarRow value={e.rating} size={16} />
                    {e.auxed && (
                      <span
                        className="inline-flex items-center"
                        style={{ color: "var(--gold)" }}
                        aria-label="Aux'd"
                      >
                        <AuxIcon filled size={18} />
                      </span>
                    )}
                  </div>

                  <div className="mt-3 flex gap-3">
                    <div
                      className="h-14 w-14 shrink-0 rounded-[4px]"
                      style={{
                        background:
                          "linear-gradient(135deg, var(--surface-secondary), var(--surface-tertiary))",
                      }}
                      aria-hidden
                    />
                    <div className="min-w-0">
                      <div
                        className="font-serif font-semibold leading-tight tracking-[-0.005em]"
                        style={{ fontSize: "18px", color: "var(--foreground)" }}
                      >
                        {e.album.title}
                      </div>
                      <div
                        className="mt-0.5 font-sans text-[13px]"
                        style={{ color: "var(--muted)" }}
                      >
                        {e.album.artist} · {e.album.year}
                      </div>
                    </div>
                  </div>

                  {e.review && (
                    <p
                      className="mt-3 font-sans text-[14px] leading-[1.55]"
                      style={{ color: "var(--foreground)" }}
                    >
                      {e.review}
                    </p>
                  )}

                  <div
                    className="mt-3 font-sans text-[13px]"
                    style={{ color: "var(--link)" }}
                  >
                    <a href="#" className="hover:underline">
                      ↗ View album
                    </a>
                  </div>
                </div>
              </article>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
