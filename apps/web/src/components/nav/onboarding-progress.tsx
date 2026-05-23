"use client";

import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";

const STEPS = [
  { slug: "step-1", label: "Welcome" },
  { slug: "step-2", label: "Follow critics" },
  { slug: "step-3", label: "First log" },
];

export function OnboardingProgress() {
  const pathname = usePathname() ?? "";
  const currentIdx = STEPS.findIndex((s) => pathname.endsWith(s.slug));
  return (
    <div className="container max-w-3xl pb-4">
      <ol className="flex items-center gap-2" aria-label="Onboarding progress">
        {STEPS.map((step, i) => {
          const reached = i <= currentIdx;
          return (
            <li key={step.slug} className="flex flex-1 items-center gap-2">
              <span
                aria-current={i === currentIdx ? "step" : undefined}
                className={cn(
                  "flex size-7 items-center justify-center rounded-full border text-xs font-medium",
                  reached
                    ? "border-foreground bg-foreground text-background"
                    : "border-border text-muted-foreground"
                )}
              >
                {i + 1}
              </span>
              <span
                className={cn("text-xs", reached ? "text-foreground" : "text-muted-foreground")}
              >
                {step.label}
              </span>
              {i < STEPS.length - 1 && (
                <span
                  aria-hidden="true"
                  className={cn("h-px flex-1", reached ? "bg-foreground" : "bg-border")}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
