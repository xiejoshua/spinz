"use client";

import { Button } from "@/components/ui/button";
import { emitOnboardingCompleted } from "@/lib/analytics";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

// Auto-redirect window — long enough to acknowledge the success state,
// short enough to feel snappy. The user can click "Go now" to skip.
const AUTO_REDIRECT_MS = 1500;

export function OnboardingComplete() {
  const router = useRouter();
  const eventFiredRef = useRef(false);

  useEffect(() => {
    if (eventFiredRef.current) return;
    eventFiredRef.current = true;
    emitOnboardingCompleted();
    const timer = window.setTimeout(() => {
      router.push("/");
    }, AUTO_REDIRECT_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [router]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
      <div className="space-y-3">
        <h2 className="text-3xl font-bold tracking-tight">You&apos;re all set</h2>
        <p className="text-sm text-muted-foreground">Building your feed…</p>
      </div>
      <Button
        type="button"
        variant="outline"
        onClick={() => {
          router.push("/");
        }}
      >
        Go now
      </Button>
    </div>
  );
}
