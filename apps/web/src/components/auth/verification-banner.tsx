"use client";

import { Button } from "@/components/ui/button";
import { useResendVerification } from "@/hooks/use-resend-verification";
import { useAuthStore } from "@/stores/auth";

/**
 * Permanent in-app reminder that the current user hasn't yet clicked
 * the link in their verification email. Renders nothing once
 * ``email_verified`` flips to true (the resend mutation does NOT
 * flip that bit — only consuming the email link does).
 *
 * Mounted in ``(app)/layout.tsx`` between the header and the page
 * children so it follows the user across every authenticated route.
 *
 * Defensive read: ``email_verified`` was added to ``SanitizedUser``
 * in this feature wave. Older session payloads or backend versions
 * that haven't been redeployed may omit the field — we treat
 * ``undefined`` as "verified" so we never spuriously badge already-
 * good users.
 */
export function VerificationBanner() {
  const user = useAuthStore((s) => s.user);
  const resend = useResendVerification();

  if (!user) return null;
  // `email_verified` is a required field on the wire post-002 but
  // tolerate undefined defensively — see file header doc.
  if (user.email_verified !== false) return null;

  return (
    <section
      role="alert"
      aria-label="Email verification required"
      className="space-y-3 px-6 py-5"
      style={{ borderBottom: "1px solid var(--separator)" }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "11px",
          letterSpacing: "0.18em",
          color: "var(--danger)",
        }}
      >
        Email unverified
      </div>
      <div className="h-px" style={{ background: "var(--danger)", opacity: 0.6 }} />
      <p
        className="pt-1 font-sans text-[14px] leading-[1.55]"
        style={{ color: "var(--foreground)", maxWidth: "60ch" }}
      >
        Verify your email to log albums, write reviews, and follow people. Check your inbox for the
        link.
      </p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
        <Button
          type="button"
          variant="destructive"
          size="sm"
          onClick={() => resend.mutate()}
          disabled={resend.isPending}
        >
          {resend.isPending ? "Sending…" : "Resend verification email"}
        </Button>
      </div>
    </section>
  );
}
