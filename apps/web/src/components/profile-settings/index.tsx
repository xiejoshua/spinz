"use client";

import { AccountSettings } from "@/components/settings/account-settings";
import { EditProfileForm } from "@/components/settings/edit-profile-form";
import Link from "next/link";

/**
 * Inline settings UI surfaced as the third tab on /profile/[handle]
 * (owner-only). Renders the existing EditProfileForm + AccountSettings
 * with editorial section dividers so avatar / display name / bio /
 * handle / email / password all live on a single canonical surface.
 *
 * The deeper /settings/* deep-link routes (privacy, notifications,
 * data export) remain in the (app)/settings shell — linked from the
 * "More" section below.
 */
export function ProfileSettings() {
  return (
    <div className="space-y-14">
      <Section
        label="Profile"
        description="Your public-facing identity on auxd. Display name + bio show up on your profile, in the feed, and on every review you write. Avatar is the same."
      >
        <EditProfileForm />
      </Section>

      <Section
        label="Account"
        description="Email + password. Both edits require your current password as a confirmation step."
      >
        <AccountSettings />
      </Section>

      <Section label="More" description="Other settings live on dedicated pages.">
        <ul className="space-y-3">
          <MoreLink
            href="/settings/privacy"
            title="Privacy"
            note="Per-entry visibility defaults, private-profile toggle, follow-requests inbox."
          />
          <MoreLink
            href="/settings/notifications"
            title="Notifications"
            note="Per-channel toggles and quiet-hours."
          />
          <MoreLink
            href="/settings/data"
            title="Data"
            note="Export everything we know about you, or close your account."
          />
        </ul>
      </Section>
    </div>
  );
}

function Section({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h2
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          {label}
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
      </div>
      {children}
    </section>
  );
}

function MoreLink({
  href,
  title,
  note,
}: {
  href: string;
  title: string;
  note: string;
}) {
  return (
    <li>
      <Link
        href={href}
        className="more-link block rounded-md p-4 transition-colors"
        style={{
          border: "1px solid var(--border)",
          background: "transparent",
          color: "var(--foreground)",
        }}
      >
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1">
            <div
              className="font-serif font-semibold tracking-[-0.005em]"
              style={{ fontSize: "16px", fontFamily: "var(--font-serif)" }}
            >
              {title}
            </div>
            <div
              className="mt-0.5 font-sans text-[13px]"
              style={{ color: "var(--muted)" }}
            >
              {note}
            </div>
          </div>
          <span
            className="shrink-0 font-mono"
            style={{ fontSize: "16px", color: "var(--muted)" }}
            aria-hidden
          >
            →
          </span>
        </div>
      </Link>
      <style>{`
        @media (hover: hover) {
          .more-link:hover {
            background: var(--surface);
          }
        }
      `}</style>
    </li>
  );
}
