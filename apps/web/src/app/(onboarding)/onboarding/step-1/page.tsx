import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function OnboardingStep1Page() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Welcome to auxd</h2>
        <p className="text-sm text-muted-foreground">
          Log albums in under 8 seconds. See what your friends are listening to. Track everything
          you’ve ever loved.
        </p>
      </div>
      <div className="space-y-2 text-sm">
        <p>You’ll set this up in three steps:</p>
        <ul className="list-inside list-disc space-y-1 text-muted-foreground">
          <li>Follow at least three critics to fill your feed</li>
          <li>Log your first album</li>
          <li>Start exploring</li>
        </ul>
      </div>
      <Button asChild className="w-full">
        <Link href="/onboarding/step-2">Continue</Link>
      </Button>
    </div>
  );
}
