"use client";

import { ProfileShell } from "@/components/diary/profile-shell";
import type { ReactNode } from "react";

type Props = {
  handle: string;
  /** Small-caps eyebrow displayed above the form, e.g. "Privacy" */
  label: string;
  /** Newsreader headline */
  title: string;
  /** One-line description in --muted */
  description?: string;
  children: ReactNode;
};

/**
 * Editorial wrapper for a single settings sub-route
 * (/profile/[handle]/settings/{privacy,notifications,data}).
 *
 * Reuses ProfileShell so the profile chrome + Settings tab nav stay
 * consistent, then renders a section header (eyebrow + headline +
 * description + hairline) above the form children.
 */
export function ProfileSettingsSection({
  handle,
  label,
  title,
  description,
  children,
}: Props) {
  return (
    <ProfileShell handle={handle} activeTab="settings">
      <section className="space-y-8">
        <header className="space-y-3">
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "11px",
              letterSpacing: "0.18em",
              color: "var(--muted)",
            }}
          >
            {label}
          </div>
          <h2
            className="font-serif font-semibold leading-[1.1] tracking-[-0.015em]"
            style={{
              fontSize: "clamp(24px, 3.5vw, 32px)",
              color: "var(--foreground)",
              fontFamily: "var(--font-serif)",
            }}
          >
            {title}
          </h2>
          <div className="h-px" style={{ background: "var(--separator)" }} />
          {description && (
            <p
              className="pt-1 font-sans text-[14px] leading-[1.55]"
              style={{ color: "var(--muted)", maxWidth: "60ch" }}
            >
              {description}
            </p>
          )}
        </header>
        {children}
      </section>
    </ProfileShell>
  );
}
