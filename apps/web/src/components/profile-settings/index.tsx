"use client";

import { AccountSettings } from "@/components/settings/account-settings";
import { EditProfileForm } from "@/components/settings/edit-profile-form";
import { Button } from "@/components/ui/button";
import { useResendVerification } from "@/hooks/use-resend-verification";
import { useAuthStore } from "@/stores/auth";
import Link from "next/link";

/**
 * Inline settings UI surfaced as the third tab on /profile/[handle]
 * (owner-only). Renders the existing EditProfileForm + AccountSettings
 * with editorial section dividers so avatar / display name / bio /
 * handle / email / password all live on a single canonical surface.
 *
 * The deeper /profile/[handle]/settings/{privacy,notifications,data}
 * routes are linked from the "More" section below.
 */
export function ProfileSettings() {
  const viewerHandle = useAuthStore((s) => s.user?.handle);
  // Base path for sub-route links. Falls back to /login if the auth
  // store hasn't hydrated yet — but the page itself is gated on
  // isOwner upstream, so this is mostly defensive.
  const base = viewerHandle ? `/profile/${viewerHandle}/settings` : "/login";
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

      <EmailVerificationSection />

      <Section label="More">
        <ul className="space-y-3">
          <MoreLink
            href={`${base}/privacy`}
            title="Privacy"
            note="Per-entry visibility defaults, private-profile toggle, follow-requests inbox."
          />
          <MoreLink
            href={`${base}/notifications`}
            title="Notifications"
            note="Per-channel toggles and quiet-hours."
          />
          <MoreLink
            href={`${base}/data`}
            title="Data"
            note="Export everything we know about you, or close your account."
          />
        </ul>
      </Section>
    </div>
  );
}

/**
 * Email-verification sub-section. Shows the user's email plus either
 * a small mono ``VERIFIED`` badge or a "Resend verification" button
 * depending on ``email_verified``. The resend button shares the same
 * mutation as the (app)-layout banner via ``useResendVerification``.
 *
 * Defensive read: treats ``email_verified === undefined`` as
 * verified, matching the banner's behavior (see verification-banner.tsx).
 */
function EmailVerificationSection() {
  const user = useAuthStore((s) => s.user);
  const resend = useResendVerification();

  if (!user) return null;
  const verified = user.email_verified !== false;

  return (
    <Section
      label="Email"
      description={
        verified
          ? "Your email is verified. Used for security alerts and password resets."
          : "Verification is required to log albums, write reviews, and follow people."
      }
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <span className="font-sans text-[14px]" style={{ color: "var(--foreground)" }}>
          {user.email}
        </span>
        {verified ? (
          <span
            className="font-mono uppercase"
            style={{
              fontSize: "11px",
              letterSpacing: "0.18em",
              color: "var(--foreground)",
            }}
          >
            Verified
          </span>
        ) : (
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => resend.mutate()}
            disabled={resend.isPending}
          >
            {resend.isPending ? "Sending…" : "Resend verification email"}
          </Button>
        )}
      </div>
    </Section>
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
            <div className="mt-0.5 font-sans text-[13px]" style={{ color: "var(--muted)" }}>
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
