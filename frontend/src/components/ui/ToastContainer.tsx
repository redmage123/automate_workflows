/**
 * Toast Container Component
 *
 * WHAT: Renders toast notifications from the toast store.
 *
 * WHY: Displays notifications in a consistent location with
 * animations and proper accessibility.
 *
 * HOW: Subscribes to toast store and renders each toast.
 */

import { useEffect, useState } from 'react';
import { useToastStore, type Toast, type ToastType } from '../../store/toastStore';

/**
 * Icon components for each toast type.
 */
const icons: Record<ToastType, React.ReactElement> = {
  success: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
        clipRule="evenodd"
      />
    </svg>
  ),
  error: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
        clipRule="evenodd"
      />
    </svg>
  ),
  warning: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
        clipRule="evenodd"
      />
    </svg>
  ),
  info: (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
      <path
        fillRule="evenodd"
        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
        clipRule="evenodd"
      />
    </svg>
  ),
};

/**
 * Color classes for each toast type.
 */
const colorClasses: Record<ToastType, { bg: string; icon: string; text: string }> = {
  success: {
    bg: 'bg-green-50',
    icon: 'text-green-400',
    text: 'text-green-800',
  },
  error: {
    bg: 'bg-red-50',
    icon: 'text-red-400',
    text: 'text-red-800',
  },
  warning: {
    bg: 'bg-yellow-50',
    icon: 'text-yellow-400',
    text: 'text-yellow-800',
  },
  info: {
    bg: 'bg-blue-50',
    icon: 'text-blue-400',
    text: 'text-blue-800',
  },
};

/**
 * Single toast component.
 */
function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [isVisible, setIsVisible] = useState(false);
  const colors = colorClasses[toast.type];

  // Animate in on mount
  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), 10);
    return () => clearTimeout(timer);
  }, []);

  // Animate out before dismiss
  const handleDismiss = () => {
    setIsVisible(false);
    setTimeout(onDismiss, 200);
  };

  return (
    <div
      className={`max-w-sm w-full ${colors.bg} shadow-lg rounded-lg pointer-events-auto ring-1 ring-black ring-opacity-5 overflow-hidden transition-all duration-200 ${
        isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-full'
      }`}
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
    >
      <div className="p-4">
        <div className="flex items-start">
          <div className={`flex-shrink-0 ${colors.icon}`}>
            {icons[toast.type]}
          </div>
          <div className="ml-3 w-0 flex-1">
            <p className={`text-sm font-medium ${colors.text}`}>{toast.title}</p>
            {toast.message && (
              <p className={`mt-1 text-sm ${colors.text} opacity-90`}>
                {toast.message}
              </p>
            )}
          </div>
          <div className="ml-4 flex-shrink-0 flex">
            <button
              onClick={handleDismiss}
              className={`inline-flex ${colors.text} opacity-70 hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-offset-2 rounded-md`}
            >
              <span className="sr-only">Close</span>
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Toast container component.
 *
 * WHAT: Renders all active toasts.
 *
 * WHY: Centralized rendering of notifications.
 *
 * HOW: Subscribes to toast store and maps toasts to components.
 */
function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div
      aria-live="assertive"
      className="fixed inset-0 flex items-end justify-end px-4 py-6 pointer-events-none sm:p-6 z-50"
    >
      <div className="flex flex-col space-y-4">
        {toasts.map((toast) => (
          <ToastItem
            key={toast.id}
            toast={toast}
            onDismiss={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </div>
  );
}

export default ToastContainer;
