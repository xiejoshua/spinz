"use client";

import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { capture } from "@/lib/posthog";
import { Share2 } from "lucide-react";

type Props = {
  url: string;
  title: string;
};

/**
 * Native OS share sheet on supporting browsers (mobile Safari, Android
 * Chrome); falls back to clipboard copy elsewhere. Tracked via PostHog
 * `review.share` so we can see which sharing surface is actually used.
 */
export function ShareButton({ url, title }: Props) {
  const { toast } = useToast();

  async function handleClick() {
    const shareData = { title, url };
    const canNativeShare =
      typeof navigator !== "undefined" &&
      typeof navigator.share === "function" &&
      // Older browsers expose `share` without `canShare`; treat as supported.
      (typeof navigator.canShare !== "function" || navigator.canShare(shareData));
    if (canNativeShare) {
      try {
        await navigator.share(shareData);
        capture("review.share", { surface: "native" });
        return;
      } catch (error) {
        // AbortError = user dismissed the sheet. Swallow silently.
        if (error instanceof DOMException && error.name === "AbortError") return;
        // Fall through to clipboard on any other failure.
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      capture("review.share", { surface: "clipboard" });
      toast({ title: "Link copied", description: "Review URL copied to your clipboard." });
    } catch {
      toast({ title: "Couldn't share", description: "Copy the URL from the address bar." });
    }
  }

  return (
    <Button type="button" variant="outline" size="sm" onClick={handleClick}>
      <Share2 className="mr-1 size-4" aria-hidden="true" />
      Share
    </Button>
  );
}
