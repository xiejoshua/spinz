import Link from "next/link";
import { SignupForm } from "./signup-form";

export default function SignupPage() {
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
          Sign up
        </div>
        <h1
          className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
          style={{
            fontSize: "clamp(32px, 5vw, 44px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          Start your diary.
        </h1>
        <p
          className="font-sans text-[16px] leading-[1.55]"
          style={{ color: "var(--muted)" }}
        >
          Log albums you've actually listened to. See what the people you
          follow played last night.
        </p>
      </div>
      <SignupForm />
      <p
        className="text-center font-sans text-sm"
        style={{ color: "var(--muted)" }}
      >
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-medium hover:underline"
          style={{ color: "var(--foreground)" }}
        >
          Log in
        </Link>
      </p>
    </div>
  );
}
