/**
 * PWA Update Prompt Component.
 *
 * WHAT: Notifies users when a new version is available.
 *
 * WHY: Ensures users get the latest features and fixes
 * while giving them control over when to update.
 *
 * HOW: Detects service worker updates via usePWA hook
 * and prompts user to refresh.
 */

import React from 'react';
import { usePWA } from '../../hooks/usePWA';

/**
 * Props for UpdatePrompt component.
 */
interface UpdatePromptProps {
  /** Callback when update is applied */
  onUpdate?: () => void;
  /** Callback when prompt is dismissed */
  onDismiss?: () => void;
}

/**
 * Update Prompt Banner Component.
 *
 * WHAT: Shows a banner when new app version is ready.
 *
 * WHY: Lets users know about updates without forcing refresh.
 *
 * @example
 * ```tsx
 * <UpdatePrompt
 *   onUpdate={() => console.log('Updating...')}
 * />
 * ```
 */
export const UpdatePrompt: React.FC<UpdatePromptProps> = ({
  onUpdate,
  onDismiss,
}) => {
  const { hasUpdate, applyUpdate } = usePWA();

  /**
   * Handle update button click.
   */
  const handleUpdate = () => {
    onUpdate?.();
    applyUpdate();
  };

  if (!hasUpdate) {
    return null;
  }

  return (
    <div
      className="fixed top-0 left-0 right-0 z-50 animate-slide-down"
      role="alert"
      aria-live="assertive"
    >
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4 flex-wrap">
          {/* Message */}
          <div className="flex items-center gap-3">
            <div className="bg-white/20 rounded-full p-1.5">
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </div>
            <div>
              <p className="text-white font-medium text-sm">
                A new version is available!
              </p>
              <p className="text-white/80 text-xs">
                Refresh to get the latest features and improvements.
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={onDismiss}
              className="px-3 py-1.5 text-white/80 hover:text-white text-sm transition-colors"
              type="button"
            >
              Later
            </button>
            <button
              onClick={handleUpdate}
              className="px-4 py-1.5 bg-white text-indigo-600 text-sm font-medium rounded-md hover:bg-gray-100 transition-colors flex items-center gap-2"
              type="button"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Refresh Now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UpdatePrompt;
