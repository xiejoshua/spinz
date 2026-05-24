"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type SanitizedUser = {
  id: string;
  handle: string;
  email: string;
  display_name: string;
  // Added in feature 002-auth-email-flows. The backend's
  // ``_public_user_payload`` ships this on every auth response
  // (login / signup / users-me / reset-password). The verification
  // banner in (app)/layout.tsx reads it to decide whether to render.
  email_verified: boolean;
};

type AuthState = {
  user: SanitizedUser | null;
  setUser: (user: SanitizedUser | null) => void;
  clear: () => void;
};

/**
 * Auth state persisted to localStorage so the user survives a hard
 * reload. The session cookie remains the source of truth for the API
 * gate (httpOnly, signed). This store just mirrors the SanitizedUser
 * payload from /api/v1/auth/login so the chrome (BottomTabs profile
 * link, avatar fallback, etc.) renders with the correct handle on
 * the first paint after refresh.
 *
 * The persisted payload contains no secrets — only public profile
 * fields (id, handle, email, display_name).
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      setUser: (user) => set({ user }),
      clear: () => set({ user: null }),
    }),
    {
      name: "auxd-auth",
      partialize: (state) => ({ user: state.user }),
    }
  )
);

export const selectUser = (state: AuthState) => state.user;
export const selectIsAuthenticated = (state: AuthState) => state.user !== null;
