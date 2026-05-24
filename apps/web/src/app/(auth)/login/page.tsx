import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { LoginForm } from "./login-form";

const SESSION_COOKIE = "auxd_session";

export default async function LoginPage() {
  // Already-logged-in users have no business on /login. The (auth)
  // layout used to do this redirect but the email-recovery pages
  // share the same shell and need to stay reachable while a session
  // cookie is set.
  const cookieStore = await cookies();
  if (cookieStore.get(SESSION_COOKIE)) {
    redirect("/feed");
  }
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
    </div>
  );
}
