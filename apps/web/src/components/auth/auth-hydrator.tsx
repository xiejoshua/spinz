"use client";

import { type SanitizedUser, useAuthStore } from "@/stores/auth";
import { useEffect } from "react";

/**
 * Synchronously seeds the Zustand auth store from a server-side fetch
 * of GET /api/v1/users/me. Mounted in (app)/layout.tsx so every
 * authenticated render has the SanitizedUser available immediately —
 * BottomTabs in particular reads `viewer.handle` to build the
 * /profile/{handle} link.
 *
 * Renders nothing. Effectively a side-effect bridge between the
 * server-rendered layout and the persisted client store.
 */
export function AuthHydrator({ user }: { user: SanitizedUser | null }) {
  useEffect(() => {
    if (user) {
      useAuthStore.getState().setUser(user);
    }
  }, [user]);
  return null;
}
