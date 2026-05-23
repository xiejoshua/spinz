"use client";

import { isPushSupported, markFirstVisit } from "@/lib/push-subscription";
import { useEffect } from "react";

// T141 — runs once per authenticated session mount. Stamps the
// first-visit timestamp (idempotent) and pre-registers the service
// worker so the OS-level push pipeline is warm by the time the user
// accepts the permission prompt.
//
// Renders nothing — pure side-effect component. Lives in (app)/layout.tsx
// so it's only mounted for signed-in users.

export function PushBootstrap() {
  useEffect(() => {
    markFirstVisit();
    if (!isPushSupported()) return;
    // Pre-register the SW silently. Failures are non-fatal — the
    // subscribe flow will re-register on demand.
    void navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      // intentionally swallow — SW registration is best-effort.
    });
  }, []);
  return null;
}
