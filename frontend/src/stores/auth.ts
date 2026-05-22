import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Organization, User } from '@/types';
import { authApi, tokenStorage } from '@/lib/api';

interface AuthState {
  user: User | null;
  organization: Organization | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    full_name: string;
    organization_name: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      organization: null,
      isAuthenticated: false,
      isLoading: false,

      async login(email, password) {
        set({ isLoading: true });
        try {
          const resp = await authApi.login({ email, password });
          tokenStorage.set(resp.tokens.access_token, resp.tokens.refresh_token);
          set({
            user: resp.user,
            organization: resp.organization,
            isAuthenticated: true,
          });
        } finally {
          set({ isLoading: false });
        }
      },

      async register(data) {
        set({ isLoading: true });
        try {
          const resp = await authApi.register(data);
          tokenStorage.set(resp.tokens.access_token, resp.tokens.refresh_token);
          set({
            user: resp.user,
            organization: resp.organization,
            isAuthenticated: true,
          });
        } finally {
          set({ isLoading: false });
        }
      },

      async logout() {
        try {
          await authApi.logout();
        } catch {
          // ignore — we're logging out anyway
        }
        tokenStorage.clear();
        set({ user: null, organization: null, isAuthenticated: false });
      },

      async refreshUser() {
        try {
          const user = await authApi.me();
          set({ user, isAuthenticated: true });
        } catch {
          set({ user: null, organization: null, isAuthenticated: false });
        }
      },

      async initialize() {
        if (!tokenStorage.getAccess()) {
          set({ isAuthenticated: false });
          return;
        }
        await get().refreshUser();
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        organization: state.organization,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
