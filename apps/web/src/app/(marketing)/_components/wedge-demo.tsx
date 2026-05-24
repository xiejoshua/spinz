"use client";

import { Button, Card } from "@heroui/react";
import { useState } from "react";
import { AuxIcon } from "@/components/icons/aux";
import { StarRating } from "@/components/icons/star-rating";

const ALBUM_OPTIONS = [
  { key: "gnx", title: "GNX", artist: "Kendrick Lamar", year: "2024", tracks: 12 },
  { key: "tpab", title: "To Pimp a Butterfly", artist: "Kendrick Lamar", year: "2015", tracks: 16 },
  { key: "damn", title: "DAMN.", artist: "Kendrick Lamar", year: "2017", tracks: 14 },
];

export function WedgeDemo() {
  const [selectedKey, setSelectedKey] = useState<string>("gnx");
  const [rating, setRating] = useState<number>(4.5);
  const [auxed, setAuxed] = useState(true);

  return (
    <section className="w-full" style={{ background: "var(--surface)" }}>
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-12 px-6 py-24 sm:py-28 lg:grid-cols-2 lg:gap-16">
        {/* Left — editorial copy */}
        <div className="lg:pt-8">
          <h2
            className="font-serif font-semibold leading-[1.1] tracking-[-0.015em]"
            style={{ fontSize: "40px", color: "var(--foreground)" }}
          >
            Eight seconds.
            <br />
            That's the deal.
          </h2>
          <div
            className="mt-6 space-y-4 font-sans text-[16px] leading-[1.65]"
            style={{ color: "var(--foreground)", maxWidth: "44ch" }}
          >
            <p>
              Search the catalog. Pick the album. Rate it on half-stars.
              Optionally Aux it as one of your standouts. Optionally write a
              review.
            </p>
            <p style={{ color: "var(--muted)" }}>
              The whole commit happens in a single sheet. No metadata walls,
              no required fields.
            </p>
          </div>
        </div>

        {/* Right — demo card */}
        <Card
          className="overflow-hidden"
          style={{
            background: "var(--background)",
            border: "1px solid var(--border)",
            boxShadow: "var(--surface-shadow)",
            borderRadius: "12px",
          }}
        >
          <div className="px-6 py-5">
            <div className="flex items-center justify-between">
              <span
                className="font-serif font-semibold tracking-[-0.01em]"
                style={{ fontSize: "18px", color: "var(--foreground)" }}
              >
                Log an album
              </span>
              <span
                className="font-mono uppercase"
                style={{ fontSize: "10px", letterSpacing: "0.15em", color: "var(--muted)" }}
              >
                Demo
              </span>
            </div>

            {/* Static "search" mockup — visual only on landing */}
            <div className="mt-5">
              <div
                className="flex items-center gap-2 rounded-lg px-3 py-2.5"
                style={{
                  background: "var(--field-background)",
                  border: "1px solid var(--field-border)",
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: "var(--muted)" }}>
                  <circle cx="11" cy="11" r="7" />
                  <path d="M21 21l-4.35-4.35" />
                </svg>
                <input
                  type="text"
                  defaultValue="kendr"
                  className="flex-1 bg-transparent font-sans text-[14px] outline-none"
                  style={{ color: "var(--foreground)" }}
                  aria-label="Search albums"
                />
              </div>
              <p
                className="mt-2 font-sans text-[11px]"
                style={{ color: "var(--muted)" }}
              >
                3 results · MusicBrainz catalog
              </p>

              <ul className="mt-2 space-y-1">
                {ALBUM_OPTIONS.map((a) => {
                  const isSelected = selectedKey === a.key;
                  return (
                    <li key={a.key}>
                      <button
                        type="button"
                        onClick={() => setSelectedKey(a.key)}
                        className="flex w-full cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-left transition-colors"
                        style={{
                          background: isSelected ? "var(--surface-secondary)" : "transparent",
                        }}
                      >
                        <div
                          className="h-9 w-9 shrink-0 rounded"
                          style={{
                            background: "linear-gradient(135deg, var(--surface-secondary), var(--surface-tertiary))",
                          }}
                          aria-hidden
                        />
                        <div className="min-w-0 flex-1">
                          <div
                            className="truncate font-sans text-[13px] font-semibold"
                            style={{ color: "var(--foreground)" }}
                          >
                            {a.title}
                          </div>
                          <div
                            className="truncate font-sans text-[11px]"
                            style={{ color: "var(--muted)" }}
                          >
                            {a.artist} · {a.year} · {a.tracks} tracks
                          </div>
                        </div>
                        {isSelected && (
                          <span style={{ color: "var(--accent)" }}>✓</span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>

            <Row label="Rate" hint="tap the left half for ½-stars">
              <StarRating value={rating} onChange={setRating} size={28} />
            </Row>

            <Row label="Aux" hint="your “this is one of my standouts” signal">
              <button
                type="button"
                onClick={() => setAuxed(!auxed)}
                aria-pressed={auxed}
                aria-label={auxed ? "Remove Aux" : "Aux this album"}
                className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--focus)]"
                style={{
                  background: auxed ? "var(--gold-soft)" : "transparent",
                  color: auxed ? "var(--gold)" : "var(--muted)",
                  border: `1px solid ${auxed ? "var(--gold)" : "var(--border)"}`,
                }}
              >
                <AuxIcon filled={auxed} size={22} />
              </button>
            </Row>

            <Row label="Visibility">
              <div
                className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 font-sans text-[13px]"
                style={{
                  background: "var(--surface-secondary)",
                  color: "var(--foreground)",
                  border: "1px solid var(--border)",
                }}
              >
                Public
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </div>
            </Row>

            <div
              className="mt-6 flex gap-3 pt-4"
              style={{ borderTop: "1px solid var(--separator)" }}
            >
              <Button variant="ghost" className="flex-1">
                Cancel
              </Button>
              <Button variant="primary" className="flex-1">
                Log →
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </section>
  );
}

function Row({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="flex items-center justify-between gap-4 py-4"
      style={{ borderBottom: "1px solid var(--separator)" }}
    >
      <div>
        <div className="font-sans text-[14px] font-medium" style={{ color: "var(--foreground)" }}>
          {label}
        </div>
        {hint && (
          <div className="mt-0.5 font-sans text-[12px]" style={{ color: "var(--muted)" }}>
            {hint}
          </div>
        )}
      </div>
      <div>{children}</div>
    </div>
  );
}
