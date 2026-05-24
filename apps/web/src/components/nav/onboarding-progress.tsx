"use client";

import { usePathname } from "next/navigation";

const STEPS = [
  { slug: "step-1", label: "Welcome" },
  { slug: "step-2", label: "Follow critics" },
  { slug: "step-3", label: "All set" },
];

/**
 * Editorial progress indicator — small-caps mono numerals connected by
 * hairlines. Active step is foreground, future steps are muted.
 */
export function OnboardingProgress() {
  const pathname = usePathname() ?? "";
  const currentIdx = STEPS.findIndex((s) => pathname.endsWith(s.slug));
  return (
    <div className="mt-6">
      <ol className="flex items-center gap-3" aria-label="Onboarding progress">
        {STEPS.map((step, i) => {
          const reached = i <= currentIdx;
          const isCurrent = i === currentIdx;
          return (
            <li key={step.slug} className="flex flex-1 items-center gap-3">
              <span
                aria-current={isCurrent ? "step" : undefined}
                className="font-mono"
                style={{
                  fontSize: "11px",
                  letterSpacing: "0.18em",
                  fontWeight: isCurrent ? 600 : 500,
                  color: reached ? "var(--foreground)" : "var(--muted)",
                  textTransform: "uppercase",
                }}
              >
                {String(i + 1).padStart(2, "0")}
                {"  "}
                {step.label}
              </span>
              {i < STEPS.length - 1 && (
                <span
                  aria-hidden="true"
                  className="h-px flex-1"
                  style={{
                    background: reached ? "var(--foreground)" : "var(--separator)",
                  }}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
