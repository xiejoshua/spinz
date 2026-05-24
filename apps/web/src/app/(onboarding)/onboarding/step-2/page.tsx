import { FollowCriticsDeck } from "@/components/onboarding/follow-critics-deck";

export default function OnboardingStep2Page() {
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
          Step two
        </div>
        <h1
          className="font-serif font-semibold leading-[1.05] tracking-[-0.02em]"
          style={{
            fontSize: "clamp(28px, 4.5vw, 40px)",
            color: "var(--foreground)",
            fontFamily: "var(--font-serif)",
          }}
        >
          Follow at least three.
        </h1>
        <p className="font-sans text-[15px] leading-[1.55]" style={{ color: "var(--muted)" }}>
          A handful of writers we picked to seed your feed. Untick anyone you don&apos;t want, then
          continue.
        </p>
      </div>
      <FollowCriticsDeck />
    </div>
  );
}
