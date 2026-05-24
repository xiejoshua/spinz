import { ResetPasswordForm } from "./reset-password-form";

/**
 * Public new-password form. The backend issues a fresh session
 * cookie on success — that's why this page stays reachable while
 * an old session cookie may still exist; the cookie set on response
 * supersedes the old one.
 */
export default async function ResetPasswordPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          Reset password
        </div>
        <h1
          className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
          style={{
            fontSize: "clamp(32px, 5vw, 44px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          Set a new password.
        </h1>
        <p className="font-sans text-[16px] leading-[1.55]" style={{ color: "var(--muted)" }}>
          At least 12 characters, including a letter and a digit. You&rsquo;ll be signed in once the
          password sticks.
        </p>
      </div>
      <ResetPasswordForm token={token} />
    </div>
  );
}
