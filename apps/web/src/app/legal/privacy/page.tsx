"use client";

import { capture } from "@/lib/posthog";
import { useEffect } from "react";

export default function PrivacyPolicyPage() {
  useEffect(() => {
    capture("legal.page_viewed", { page: "privacy" });
  }, []);

  return (
    <article className="prose prose-neutral max-w-none space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Privacy policy</h1>
        <p className="text-sm text-muted-foreground">Last updated: placeholder draft</p>
      </header>

      <aside
        data-testid="placeholder-banner"
        className="rounded-md border border-amber-400/40 bg-amber-50 p-4 text-sm text-amber-900"
      >
        <strong>Placeholder.</strong> The final policy will be lawyer-reviewed before public launch.
        The text below is a working sketch and is not legally binding.
      </aside>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Data we collect</h2>
        <p className="text-sm">
          We collect the information you give us when you create an account (email, handle, display
          name) and the activity you generate inside the product (diary entries, reviews, follows,
          blocks, and notification preferences). We also keep server-side observability data — IP,
          user agent, request timings — to operate the service.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">How we use it</h2>
        <p className="text-sm">
          Your data powers the social product. We do not sell it. We use a small set of vendors
          (Resend for transactional email, PostHog for product analytics, Sentry for error
          reporting, Cloudflare R2 for storage) under standard data-processing agreements.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Your rights</h2>
        <p className="text-sm">
          You can export every row we hold about you from Settings - Data, and you can schedule your
          account for deletion the same way. Deletion runs after a 30-day grace window during which
          you can cancel.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Contact</h2>
        <p className="text-sm">
          Reach us at <a href="mailto:privacy@auxd.xiejoshua.com">privacy@auxd.xiejoshua.com</a> for
          any privacy-related question.
        </p>
      </section>
    </article>
  );
}
