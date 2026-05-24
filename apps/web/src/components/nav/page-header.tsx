import type { ReactNode } from "react";

type Props = {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  className?: string;
};

/**
 * Editorial page header — small-caps mono eyebrow, Newsreader serif
 * headline, optional subtitle in --muted Inter Tight.
 *
 * Used across the (app) shell so every interior surface picks up the
 * same typographic register as the landing.
 */
export function PageHeader({ eyebrow, title, subtitle, className }: Props) {
  return (
    <header className={className}>
      {eyebrow && (
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
      )}
      <h1
        className="mt-2 font-serif font-semibold leading-[1.05] tracking-[-0.015em]"
        style={{
          fontSize: "clamp(28px, 4vw, 36px)",
          color: "var(--foreground)",
          fontFamily: "var(--font-serif)",
        }}
      >
        {title}
      </h1>
      {subtitle && (
        <p
          className="mt-3 font-sans text-[15px] leading-[1.55]"
          style={{ color: "var(--muted)", maxWidth: "60ch" }}
        >
          {subtitle}
        </p>
      )}
    </header>
  );
}
