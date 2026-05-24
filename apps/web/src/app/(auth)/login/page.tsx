import Link from "next/link";
import { LoginForm } from "./login-form";

export default function LoginPage() {
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
          Log in
        </div>
        <h1
          className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
          style={{
            fontSize: "clamp(32px, 5vw, 44px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          Welcome back.
        </h1>
      </div>
      <LoginForm />
      <p className="text-center font-sans text-sm" style={{ color: "var(--muted)" }}>
        New here?{" "}
        <Link
          href="/signup"
          className="font-medium hover:underline"
          style={{ color: "var(--foreground)" }}
        >
          Create an account
        </Link>
      </p>
    </div>
  );
}
