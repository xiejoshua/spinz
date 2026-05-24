"use client";

import { Button } from "@/components/ui/button";
import { markOnboardingStart } from "@/lib/analytics";
import Link from "next/link";
import { useEffect } from "react";

export function OnboardingStep1Intro() {
  useEffect(() => {
    markOnboardingStart();
  }, []);

  return (
    <div className="space-y-8 pt-8">
      <div className="space-y-3">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          Welcome
        </div>
        <h1
          className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
          style={{
            fontSize: "clamp(32px, 5vw, 44px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          A diary to bring back albums as{" "}
          <em className="italic" style={{ fontFamily: "var(--font-serif)" }}>
            art
          </em>
          .
        </h1>
        <p
          className="font-sans text-[16px] leading-[1.55]"
          style={{ color: "var(--muted)" }}
        >
          Log albums in under eight seconds. See what the people you follow
          played last night.
        </p>
      </div>

      <div className="space-y-2">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          Three steps
        </div>
        <ul className="space-y-1.5 pt-1 font-sans text-[15px]" style={{ color: "var(--foreground)" }}>
          <li>— Follow at least three critics to fill your feed.</li>
          <li>— Log your first album.</li>
          <li>— Start exploring.</li>
        </ul>
      </div>

      <Button asChild className="w-full">
        <Link href="/onboarding/step-2">Continue</Link>
      </Button>
    </div>
  );
}
