/**
 * Toast Notification Store
 *
 * WHAT: Zustand store for managing toast notifications.
 *
 * WHY: Centralized state management for notifications that can be
 * triggered from anywhere in the app (components, services, etc.).
 *
 * HOW: Simple queue-based system with auto-dismiss functionality.
 */

import { create } from 'zustand';

/**
 * Toast notification types.
 */
export type ToastType = 'success' | 'error' | 'warning' | 'info';

/**
 * Toast notification interface.
 */
export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

/**
 * Toast store state interface.
 */
interface ToastState {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  clearToasts: () => void;
}

/**
 * Generate unique ID for toast.
 */
function generateId(): string {
  return `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Default duration by toast type (milliseconds).
 */
const DEFAULT_DURATIONS: Record<ToastType, number> = {
  success: 3000,
  error: 5000,
  warning: 4000,
  info: 3000,
};

/**
 * Toast store.
 *
 * WHAT: Manages toast notification state.
 *
 * WHY: Allows any component to trigger notifications without
 * prop drilling or context providers.
 *
 * HOW: Uses zustand for minimal boilerplate state management.
 */
export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  /**
   * Add a new toast notification.
   *
   * WHAT: Creates toast and auto-schedules removal.
   *
   * WHY: Simple API for showing notifications.
   */
  addToast: (toast) => {
    const id = generateId();
    const duration = toast.duration ?? DEFAULT_DURATIONS[toast.type];

    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }],
    }));

    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, duration);
    }
  },

  /**
   * Remove a specific toast.
   */
  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),

  /**
   * Clear all toasts.
   */
  clearToasts: () => set({ toasts: [] }),
}));

/**
 * Convenience functions for common toast types.
 *
 * WHAT: Helper functions for triggering specific toast types.
 *
 * WHY: Cleaner API than always specifying type.
 */
export const toast = {
  success: (title: string, message?: string) =>
    useToastStore.getState().addToast({ type: 'success', title, message }),

  error: (title: string, message?: string) =>
    useToastStore.getState().addToast({ type: 'error', title, message }),

  warning: (title: string, message?: string) =>
    useToastStore.getState().addToast({ type: 'warning', title, message }),

  info: (title: string, message?: string) =>
    useToastStore.getState().addToast({ type: 'info', title, message }),
};

export default useToastStore;
