/**
 * Store Index
 *
 * WHAT: Central export point for all Zustand stores.
 *
 * WHY: Single import path for store access across components.
 *
 * HOW: Re-exports all stores and selectors.
 */

export { useAuthStore, selectUser, selectOrganization, selectIsAuthenticated, selectIsLoading, selectError, selectIsAdmin } from './authSlice';
export { useToastStore, toast } from './toastStore';
export type { Toast, ToastType } from './toastStore';
