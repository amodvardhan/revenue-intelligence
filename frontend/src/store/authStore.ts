import { create } from "zustand";
import { persist } from "zustand/middleware";

import { setAuthToken } from "@/services/api";

interface AuthState {
  token: string | null;
  email: string | null;
  setSession: (token: string | null, email: string | null) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      email: null,
      setSession: (token, email) => {
        setAuthToken(token);
        set({ token, email });
      },
      clear: () => {
        setAuthToken(null);
        set({ token: null, email: null });
      },
    }),
    {
      name: "rip-auth",
      partialize: (s) => ({ token: s.token, email: s.email }),
      onRehydrateStorage: () => (state) => {
        if (state?.token) setAuthToken(state.token);
      },
    },
  ),
);
