import { FollowCriticsDeck } from "@/components/onboarding/follow-critics-deck";

export default function OnboardingStep2Page() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Follow at least 3 critics</h2>
        <p className="text-sm text-muted-foreground">
          We pre-picked a handful of taste-makers to fill your feed. Untick anyone you don&apos;t
          want, then hit Continue.
        </p>
      </div>
      <FollowCriticsDeck />
    </div>
  );
}
