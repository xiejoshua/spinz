import { ForgotPasswordForm } from "./forgot-password-form";

/**
 * Public password-reset request page.
 *
 * Stays reachable while a session cookie is set — a user who's
 * logged in but forgot their old password might still land here.
 *
 * The form component owns the eyebrow + headline + description so it
 * can swap them atomically when the user moves from the request state
 * to the "check your inbox" success state.
 */
export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
