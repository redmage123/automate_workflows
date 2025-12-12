/**
 * PWA Install Prompt Component.
 *
 * WHAT: Displays an install prompt banner for the PWA.
 *
 * WHY: Encourages users to install the app for:
 * - Better performance
 * - Offline access
 * - Push notifications
 * - App-like experience
 *
 * HOW: Uses usePWA hook to detect install capability
 * and handle the installation process.
 */

import React, { useState, useEffect } from 'react';
import { usePWA } from '../../hooks/usePWA';

/**
 * Props for InstallPrompt component.
 */
interface InstallPromptProps {
  /** Delay before showing prompt (ms) */
  delay?: number;
  /** Callback when prompt is dismissed */
  onDismiss?: () => void;
  /** Callback when app is installed */
  onInstall?: () => void;
}

/**
 * Install Prompt Banner Component.
 *
 * WHAT: Shows a dismissible banner prompting installation.
 *
 * WHY: Non-intrusive way to suggest installing the PWA.
 *
 * @example
 * ```tsx
 * <InstallPrompt
 *   delay={5000}
 *   onInstall={() => analytics.track('pwa_installed')}
 * />
 * ```
 */
export const InstallPrompt: React.FC<InstallPromptProps> = ({
  delay = 3000,
  onDismiss,
  onInstall,
}) => {
  const { canInstall, promptInstall } = usePWA();
  const [show, setShow] = useState(false);
  const [installing, setInstalling] = useState(false);

  // Show prompt after delay
  useEffect(() => {
    if (!canInstall) {
      setShow(false);
      return;
    }

    // Check if user previously dismissed
    const dismissed = localStorage.getItem('pwa-install-dismissed');
    if (dismissed) {
      const dismissedAt = new Date(dismissed);
      const daysSinceDismissed =
        (Date.now() - dismissedAt.getTime()) / (1000 * 60 * 60 * 24);
      // Show again after 7 days
      if (daysSinceDismissed < 7) {
        return;
      }
    }

    const timer = setTimeout(() => {
      setShow(true);
    }, delay);

    return () => clearTimeout(timer);
  }, [canInstall, delay]);

  /**
   * Handle install button click.
   */
  const handleInstall = async () => {
    setInstalling(true);
    const installed = await promptInstall();
    setInstalling(false);

    if (installed) {
      setShow(false);
      onInstall?.();
    }
  };

  /**
   * Handle dismiss button click.
   */
  const handleDismiss = () => {
    setShow(false);
    localStorage.setItem('pwa-install-dismissed', new Date().toISOString());
    onDismiss?.();
  };

  if (!show) {
    return null;
  }

  return (
    <div
      className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 z-50 animate-slide-up"
      role="alert"
      aria-live="polite"
    >
      <div className="bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="bg-white/20 rounded-lg p-2">
              <svg
                className="w-6 h-6 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
                />
              </svg>
            </div>
            <div>
              <h3 className="text-white font-semibold text-sm">
                Install Automation Platform
              </h3>
              <p className="text-white/80 text-xs">
                Get a better experience
              </p>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="px-4 py-3">
          <ul className="space-y-2 text-sm text-gray-600">
            <li className="flex items-center gap-2">
              <svg
                className="w-4 h-4 text-green-500 flex-shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
              <span>Works offline</span>
            </li>
            <li className="flex items-center gap-2">
              <svg
                className="w-4 h-4 text-green-500 flex-shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
              <span>Faster loading</span>
            </li>
            <li className="flex items-center gap-2">
              <svg
                className="w-4 h-4 text-green-500 flex-shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
              <span>Push notifications</span>
            </li>
          </ul>
        </div>

        {/* Actions */}
        <div className="px-4 py-3 bg-gray-50 flex items-center justify-end gap-2">
          <button
            onClick={handleDismiss}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            type="button"
          >
            Not now
          </button>
          <button
            onClick={handleInstall}
            disabled={installing}
            className="px-4 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            type="button"
          >
            {installing ? (
              <>
                <svg
                  className="w-4 h-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Installing...
              </>
            ) : (
              <>
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
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
                Install
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default InstallPrompt;
