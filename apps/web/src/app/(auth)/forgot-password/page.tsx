import { ForgotPasswordForm } from "./forgot-password-form";

/**
 * Public password-reset request page.
 *
 * Stays reachable while a session cookie is set — a user who's
 * logged in but forgot their old password might still land here.
 */
export default function ForgotPasswordPage() {
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
          Forgot password
        </div>
        <h1
          className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
          style={{
            fontSize: "clamp(32px, 5vw, 44px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          Reset your password.
        </h1>
        <p className="font-sans text-[16px] leading-[1.55]" style={{ color: "var(--muted)" }}>
          Enter the email on your account. We&rsquo;ll send a link to set a new password.
        </p>
      </div>
      <ForgotPasswordForm />
    </div>
  );
}
