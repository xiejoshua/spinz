import type { ReactNode } from "react";

type Props = {
  eyebrow: string;
  headline: string;
  trailing?: ReactNode;
  children: ReactNode;
};

/**
 * Editorial section wrapper used across the new Discover front page.
 * Mirrors the mono-eyebrow + Newsreader-headline + 48px hairline
 * pattern already used in feed/profile/email so every Discover
 * section reads as part of the same publication.
 *
 * `trailing` is an optional right-aligned slot for a link (e.g.
 * "See all popular →") that sits on the same row as the headline.
 */
export function SectionShell({ eyebrow, headline, trailing, children }: Props) {
  return (
    <section>
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "11px",
          letterSpacing: "0.18em",
          color: "var(--muted)",
        }}
      >
        {eyebrow}
      </div>
      <div className="mt-2 flex items-baseline justify-between gap-4">
        <h2
          className="font-serif font-semibold leading-[1.1] tracking-[-0.012em]"
          style={{
            fontSize: "clamp(20px, 2.6vw, 24px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          {headline}
        </h2>
        {trailing && (
          <div className="font-sans text-[13px]" style={{ color: "var(--muted)" }}>
            {trailing}
          </div>
        )}
      </div>
      <div
        aria-hidden="true"
        className="mt-3 mb-6"
        style={{
          height: "1px",
          width: "48px",
          background: "var(--separator)",
        }}
      />
      {children}
    </section>
  );
}
