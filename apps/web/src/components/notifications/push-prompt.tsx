"use client";

import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { capture } from "@/lib/posthog";
import {
  getCurrentPermission,
  isPushSupported,
  markDismissed,
  readDismissedAt,
  readFirstVisitAt,
  readFollowsCount,
  shouldShowPushPrompt,
  subscribeToPush,
} from "@/lib/push-subscription";
import { Bell, X } from "lucide-react";
import { useEffect, useState } from "react";

// T141 — non-modal banner that only renders when the user has crossed the
// activity gate (3+ follows OR 7+ days since first visit) AND has not
// dismissed recently AND the browser hasn't already been answered.
//
// Mount inside /notifications (not as a global overlay) per taxonomy doc
// §Push line 114: "not on first session, too aggressive".

export function PushPrompt() {
  const { toast } = useToast();
  const [render, setRender] = useState(false);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!isPushSupported()) {
      setRender(false);
      return;
    }
    if (getCurrentPermission() !== "default") {
      setRender(false);
      return;
    }
    const eligible = shouldShowPushPrompt({
      followsCount: readFollowsCount(),
      firstVisitAt: readFirstVisitAt(),
      dismissedAt: readDismissedAt(),
      now: Date.now(),
    });
    if (eligible) {
      setRender(true);
      capture("push.prompt_shown");
    }
  }, []);

  if (!render) return null;

  async function handleEnable() {
    setPending(true);
    const result = await subscribeToPush();
    setPending(false);
    if (result.ok) {
      capture("push.permission_granted", { created: result.created });
      toast({ title: "Push notifications enabled" });
      setRender(false);
      return;
    }
    if (result.reason === "denied") {
      capture("push.permission_denied");
      toast({
        title: "Notifications blocked",
        description: "Enable them in your browser settings to turn this on later.",
      });
      setRender(false);
      return;
    }
    capture("push.subscribe_failed", { reason: result.reason });
    toast({
      title: "Could not enable push",
      description: "Please try again in a moment.",
    });
  }

  function handleDismiss() {
    markDismissed();
    capture("push.dismissed");
    setRender(false);
  }

  return (
    <aside
      className="flex items-start gap-3 rounded-md border bg-card p-3 text-sm"
      aria-label="Enable push notifications"
    >
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Bell className="size-4" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="space-y-0.5">
          <p className="font-medium">Get notified on activity that matters</p>
          <p className="text-xs text-muted-foreground">
            Enable push for follows and review likes. You can change this any time in settings.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            disabled={pending}
            onClick={() => {
              void handleEnable();
            }}
          >
            {pending ? "Enabling…" : "Enable push notifications"}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={handleDismiss}>
            Not now
          </Button>
        </div>
      </div>
      <button
        type="button"
        aria-label="Dismiss"
        onClick={handleDismiss}
        className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </aside>
  );
}
