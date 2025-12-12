/**
 * Authentication State Store
 *
 * WHAT: Zustand store for authentication state management.
 *
 * WHY: Centralized auth state provides:
 * - Single source of truth for user/auth data
 * - Reactive updates across components
 * - Persistence of auth state
 * - Clean separation from component logic
 *
 * HOW: Zustand store with actions for login, logout, and state updates.
 * Persists to localStorage for session continuity.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type {
  AuthState,
  User,
  Organization,
  LoginRequest,
  RegisterRequest,
  ApiError,
} from '../types';
import * as authService from '../services/auth';
import { clearTokens, getAccessToken } from '../services/api';

/**
 * Type guard for API error objects
 *
 * WHAT: Checks if an unknown error is an ApiError from the backend.
 *
 * WHY: The backend returns structured error responses with helpful
 * messages. We need to extract these for user-friendly error display.
 *
 * HOW: Check for the presence of 'message' and 'error' properties
 * which are always present in ApiError responses.
 */
function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    'error' in error
  );
}

/**
 * Extract user-friendly error message from various error types
 *
 * WHAT: Converts different error formats into readable messages.
 *
 * WHY: Errors can come from the API (ApiError), network issues (Error),
 * or other sources. Users need clear, actionable messages.
 *
 * HOW: Check error type and extract the most helpful message available.
 */
function getErrorMessage(error: unknown, fallback: string): string {
  if (isApiError(error)) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

/**
 * Extended auth state with actions
 *
 * WHY: Combines state and actions in single interface
 * for complete store type definition.
 */
interface AuthStore extends AuthState {
  // Actions
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  loadUser: () => Promise<void>;
  setUser: (user: User) => void;
  setOrganization: (org: Organization) => void;
  setError: (error: string | null) => void;
  clearAuth: () => void;
}

/**
 * Initial state
 *
 * WHY: Default values for auth state before any user action.
 */
const initialState: AuthState = {
  user: null,
  organization: null,
  tokens: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
};

/**
 * Auth store
 *
 * WHAT: Zustand store for authentication.
 *
 * WHY: Provides reactive state management with persistence.
 *
 * HOW: Uses zustand with persist middleware for localStorage.
 * Actions call auth service and update state atomically.
 */
export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      ...initialState,

      /**
       * Login action
       *
       * WHAT: Authenticate user and load profile.
       *
       * WHY: Complete login flow including user/org data fetch.
       *
       * HOW: Call login API, store tokens, fetch user and org.
       */
      login: async (credentials: LoginRequest) => {
        set({ isLoading: true, error: null });

        try {
          const tokens = await authService.login(credentials);
          set({ tokens, isAuthenticated: true });

          // Load user and organization data
          const [user, organization] = await Promise.all([
            authService.getCurrentUser(),
            authService.getCurrentOrganization(),
          ]);

          set({
            user,
            organization,
            isLoading: false,
          });
        } catch (error) {
          const message = getErrorMessage(error, 'Login failed. Please check your credentials.');
          set({
            isLoading: false,
            error: message,
            isAuthenticated: false,
            tokens: null,
          });
          throw error;
        }
      },

      /**
       * Register action
       *
       * WHAT: Create new user and organization.
       *
       * WHY: Self-service registration for new clients.
       *
       * HOW: Call register API. Note: Does not auto-login;
       * user must verify email first.
       */
      register: async (data: RegisterRequest) => {
        set({ isLoading: true, error: null });

        try {
          await authService.register(data);
          set({ isLoading: false });
        } catch (error) {
          const message = getErrorMessage(error, 'Registration failed. Please try again.');
          set({ isLoading: false, error: message });
          throw error;
        }
      },

      /**
       * Logout action
       *
       * WHAT: End user session.
       *
       * WHY: Clear all auth state and tokens.
       *
       * HOW: Call logout API, clear tokens, reset state.
       */
      logout: async () => {
        set({ isLoading: true });

        try {
          await authService.logout();
        } finally {
          // Always clear state, even if API call fails
          clearTokens();
          set({ ...initialState, isLoading: false });
        }
      },

      /**
       * Load user action
       *
       * WHAT: Fetch current user data.
       *
       * WHY: Called on app init to restore session.
       *
       * HOW: Check for token, fetch user/org if present.
       */
      loadUser: async () => {
        const token = getAccessToken();
        if (!token) {
          set({ ...initialState });
          return;
        }

        set({ isLoading: true });

        try {
          const [user, organization] = await Promise.all([
            authService.getCurrentUser(),
            authService.getCurrentOrganization(),
          ]);

          set({
            user,
            organization,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch {
          // Token invalid or expired
          clearTokens();
          set({ ...initialState, isLoading: false });
        }
      },

      /**
       * Set user
       *
       * WHAT: Update user in state.
       *
       * WHY: Allow external updates (e.g., profile edit).
       */
      setUser: (user: User) => {
        set({ user });
      },

      /**
       * Set organization
       *
       * WHAT: Update organization in state.
       *
       * WHY: Allow external updates (e.g., org settings change).
       */
      setOrganization: (organization: Organization) => {
        set({ organization });
      },

      /**
       * Set error
       *
       * WHAT: Update error state.
       *
       * WHY: Allow components to clear or set errors.
       */
      setError: (error: string | null) => {
        set({ error });
      },

      /**
       * Clear auth
       *
       * WHAT: Reset all auth state.
       *
       * WHY: Complete state reset without API call.
       */
      clearAuth: () => {
        clearTokens();
        set({ ...initialState });
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      // Only persist specific fields
      partialize: (state) => ({
        user: state.user,
        organization: state.organization,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

/**
 * Selectors
 *
 * WHY: Memoized selectors for common state access patterns.
 */
export const selectUser = (state: AuthStore) => state.user;
export const selectOrganization = (state: AuthStore) => state.organization;
export const selectIsAuthenticated = (state: AuthStore) => state.isAuthenticated;
export const selectIsLoading = (state: AuthStore) => state.isLoading;
export const selectError = (state: AuthStore) => state.error;
export const selectIsAdmin = (state: AuthStore) => state.user?.role === 'ADMIN';
