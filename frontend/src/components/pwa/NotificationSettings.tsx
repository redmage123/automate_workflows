/**
 * Notification Settings Component.
 *
 * WHAT: UI for managing push notification preferences.
 *
 * WHY: Gives users control over:
 * - Enabling/disabling push notifications
 * - Understanding notification status
 * - Managing notification permissions
 *
 * HOW: Uses usePWA hook for push subscription management.
 */

import React, { useState } from 'react';
import { usePWA } from '../../hooks/usePWA';

/**
 * Props for NotificationSettings component.
 */
interface NotificationSettingsProps {
  /** Whether to show as a card or inline */
  variant?: 'card' | 'inline';
  /** Callback when notifications are enabled */
  onEnable?: () => void;
  /** Callback when notifications are disabled */
  onDisable?: () => void;
}

/**
 * Notification Settings Component.
 *
 * WHAT: Controls for push notification subscription.
 *
 * WHY: User-friendly notification management.
 *
 * @example
 * ```tsx
 * <NotificationSettings
 *   variant="card"
 *   onEnable={() => toast.success('Notifications enabled!')}
 * />
 * ```
 */
export const NotificationSettings: React.FC<NotificationSettingsProps> = ({
  variant = 'card',
  onEnable,
  onDisable,
}) => {
  const {
    pushSupported,
    notificationPermission,
    requestNotificationPermission,
    subscribeToPush,
    unsubscribeFromPush,
  } = usePWA();

  const [loading, setLoading] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Handle enable notifications.
   */
  const handleEnable = async () => {
    setLoading(true);
    setError(null);

    try {
      // Request permission first
      const permissionGranted = await requestNotificationPermission();
      if (!permissionGranted) {
        setError('Notification permission denied');
        return;
      }

      // Subscribe to push
      const subscription = await subscribeToPush();
      if (subscription) {
        setSubscribed(true);
        onEnable?.();
      } else {
        setError('Failed to subscribe to notifications');
      }
    } catch (err) {
      setError('An error occurred while enabling notifications');
      console.error('Notification enable error:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handle disable notifications.
   */
  const handleDisable = async () => {
    setLoading(true);
    setError(null);

    try {
      const success = await unsubscribeFromPush();
      if (success) {
        setSubscribed(false);
        onDisable?.();
      } else {
        setError('Failed to unsubscribe from notifications');
      }
    } catch (err) {
      setError('An error occurred while disabling notifications');
      console.error('Notification disable error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Not supported message
  if (!pushSupported) {
    return (
      <div className={variant === 'card' ? 'bg-gray-50 rounded-lg p-4' : ''}>
        <div className="flex items-center gap-3 text-gray-500">
          <svg
            className="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            />
          </svg>
          <span className="text-sm">
            Push notifications are not supported in this browser.
          </span>
        </div>
      </div>
    );
  }

  // Permission denied message
  if (notificationPermission === 'denied') {
    return (
      <div className={variant === 'card' ? 'bg-red-50 rounded-lg p-4' : ''}>
        <div className="flex items-start gap-3">
          <div className="bg-red-100 rounded-full p-2 flex-shrink-0">
            <svg
              className="w-5 h-5 text-red-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
              />
            </svg>
          </div>
          <div>
            <p className="text-red-800 font-medium text-sm">
              Notifications Blocked
            </p>
            <p className="text-red-600 text-xs mt-1">
              You've blocked notifications. To enable them, update your browser
              settings for this site.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const containerClasses = variant === 'card'
    ? 'bg-white rounded-lg border border-gray-200 p-4 shadow-sm'
    : '';

  return (
    <div className={containerClasses}>
      <div className="flex items-start justify-between gap-4">
        {/* Info */}
        <div className="flex items-start gap-3">
          <div className={`rounded-full p-2 flex-shrink-0 ${
            subscribed ? 'bg-green-100' : 'bg-gray-100'
          }`}>
            <svg
              className={`w-5 h-5 ${
                subscribed ? 'text-green-600' : 'text-gray-600'
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
              />
            </svg>
          </div>
          <div>
            <p className="text-gray-900 font-medium text-sm">
              Push Notifications
            </p>
            <p className="text-gray-500 text-xs mt-0.5">
              {subscribed
                ? 'You will receive notifications for important updates.'
                : 'Get notified about tickets, proposals, and payments.'}
            </p>
          </div>
        </div>

        {/* Toggle */}
        <button
          onClick={subscribed ? handleDisable : handleEnable}
          disabled={loading}
          className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${
            subscribed ? 'bg-indigo-600' : 'bg-gray-200'
          }`}
          type="button"
          role="switch"
          aria-checked={subscribed}
          aria-label="Enable push notifications"
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
              subscribed ? 'translate-x-5' : 'translate-x-0'
            }`}
          >
            {loading && (
              <svg
                className="w-5 h-5 animate-spin text-gray-400"
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
            )}
          </span>
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="mt-3 flex items-center gap-2 text-red-600 text-xs">
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
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          {error}
        </div>
      )}

      {/* Additional info */}
      {variant === 'card' && (
        <div className="mt-4 pt-3 border-t border-gray-100">
          <p className="text-gray-400 text-xs">
            You can change this setting anytime. We'll only send important
            notifications about your account activity.
          </p>
        </div>
      )}
    </div>
  );
};

export default NotificationSettings;
