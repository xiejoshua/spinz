"use client";

import { capture } from "@/lib/posthog";
import { useEffect } from "react";

export default function TermsOfServicePage() {
  useEffect(() => {
    capture("legal.page_viewed", { page: "terms" });
  }, []);

  return (
    <article className="prose prose-neutral max-w-none space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Terms of service</h1>
        <p className="text-sm text-muted-foreground">Last updated: placeholder draft</p>
      </header>

      <aside
        data-testid="placeholder-banner"
        className="rounded-md border border-amber-400/40 bg-amber-50 p-4 text-sm text-amber-900"
      >
        <strong>Placeholder.</strong> The final terms will be lawyer-reviewed before public launch.
        The text below is a working sketch and is not legally binding.
      </aside>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Acceptance</h2>
        <p className="text-sm">
          By creating an account you agree to these terms. If you don't agree, please don't sign up.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Use of service</h2>
        <p className="text-sm">
          Be civil. Don't harass other users, don't spam, don't impersonate anyone. We reserve the
          right to suspend or remove accounts that violate this in either direction.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Account termination</h2>
        <p className="text-sm">
          You can delete your account any time from Settings - Data with a 30-day grace window. We
          can suspend or terminate accounts that repeatedly violate the rules above; appeals go to{" "}
          <a href="mailto:appeals@auxd.xiejoshua.com">appeals@auxd.xiejoshua.com</a>.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Liability</h2>
        <p className="text-sm">
          auxd is provided as-is, without warranty. We're not liable for indirect damages arising
          from your use of the product.
        </p>
      </section>
    </article>
  );
}
