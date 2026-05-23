import Link from "next/link";
import { LoginForm } from "./login-form";

export default function LoginPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Log in</h1>
        <p className="text-sm text-muted-foreground">Welcome back to auxd.</p>
      </div>
      <LoginForm />
      <p className="text-sm text-muted-foreground">
        New here?{" "}
        <Link href="/signup" className="font-medium text-foreground hover:underline">
          Create an account
        </Link>
      </p>
    </div>
  );
}
