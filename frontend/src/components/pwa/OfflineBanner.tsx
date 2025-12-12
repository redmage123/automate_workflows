/**
 * Offline Banner Component.
 *
 * WHAT: Displays a banner when the user is offline.
 *
 * WHY: Informs users about connectivity status
 * so they understand any limitations.
 *
 * HOW: Uses usePWA hook to detect online/offline status.
 */

import React from 'react';
import { usePWA } from '../../hooks/usePWA';

/**
 * Props for OfflineBanner component.
 */
interface OfflineBannerProps {
  /** Position of the banner */
  position?: 'top' | 'bottom';
  /** Custom message to display */
  message?: string;
}

/**
 * Offline Status Banner Component.
 *
 * WHAT: Shows a banner when user loses connectivity.
 *
 * WHY: Transparency about network status prevents confusion.
 *
 * @example
 * ```tsx
 * <OfflineBanner
 *   position="bottom"
 *   message="You're offline. Some features may not work."
 * />
 * ```
 */
export const OfflineBanner: React.FC<OfflineBannerProps> = ({
  position = 'bottom',
  message = "You're offline. Some features may be limited.",
}) => {
  const { isOnline } = usePWA();

  if (isOnline) {
    return null;
  }

  const positionClasses = position === 'top'
    ? 'top-0'
    : 'bottom-0';

  return (
    <div
      className={`fixed left-0 right-0 ${positionClasses} z-40 animate-slide-up`}
      role="status"
      aria-live="polite"
    >
      <div className="bg-amber-500 px-4 py-2">
        <div className="max-w-7xl mx-auto flex items-center justify-center gap-2">
          {/* Offline Icon */}
          <svg
            className="w-5 h-5 text-amber-900"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414"
            />
          </svg>

          {/* Message */}
          <span className="text-amber-900 text-sm font-medium">
            {message}
          </span>

          {/* Pulsing dot indicator */}
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-700 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-700"></span>
          </span>
        </div>
      </div>
    </div>
  );
};

export default OfflineBanner;
