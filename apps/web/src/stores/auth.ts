"use client";

import { create } from "zustand";

export type SanitizedUser = {
  id: string;
  handle: string;
  email: string;
  display_name: string;
};

type AuthState = {
  user: SanitizedUser | null;
  setUser: (user: SanitizedUser | null) => void;
  clear: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  clear: () => set({ user: null }),
}));

export const selectUser = (state: AuthState) => state.user;
export const selectIsAuthenticated = (state: AuthState) => state.user !== null;
