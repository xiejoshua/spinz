"use client";

import { Button } from "@/components/ui/button";
import { emitOnboardingCompleted } from "@/lib/analytics";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

const AUTO_REDIRECT_MS = 1500;

export function OnboardingComplete() {
  const router = useRouter();
  const eventFiredRef = useRef(false);

  useEffect(() => {
    if (eventFiredRef.current) return;
    eventFiredRef.current = true;
    emitOnboardingCompleted();
    const timer = window.setTimeout(() => {
      router.push("/feed");
    }, AUTO_REDIRECT_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [router]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 pt-16 text-center">
      <div className="space-y-3">
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "11px",
            letterSpacing: "0.18em",
            color: "var(--muted)",
          }}
        >
          All set
        </div>
        <h1
          className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
          style={{
            fontSize: "clamp(32px, 5vw, 44px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          You&apos;re in.
        </h1>
        <p
          className="font-sans text-[15px]"
          style={{ color: "var(--muted)" }}
        >
          Building your feed…
        </p>
      </div>
      <Button
        type="button"
        variant="outline"
        onClick={() => {
          router.push("/feed");
        }}
      >
        Go now
      </Button>
    </div>
  );
}
