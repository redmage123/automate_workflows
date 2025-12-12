/**
 * PWA Hook for managing Progressive Web App features.
 *
 * WHAT: Custom hook for PWA functionality including:
 * - Installation prompt
 * - Push notifications
 * - Offline detection
 * - Update notifications
 *
 * WHY: Centralizes PWA logic for:
 * - Consistent install prompts across the app
 * - Push notification management
 * - Offline status awareness
 * - Seamless updates
 *
 * HOW: Uses browser APIs and Service Worker communication
 * to provide reactive PWA state and actions.
 */

import { useState, useEffect, useCallback } from 'react';

/**
 * PWA installation prompt event.
 */
interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: 'accepted' | 'dismissed';
    platform: string;
  }>;
  prompt(): Promise<void>;
}

/**
 * Push notification permission state.
 */
type NotificationPermission = 'default' | 'granted' | 'denied';

/**
 * PWA state interface.
 */
interface PWAState {
  /** Whether the app can be installed */
  canInstall: boolean;
  /** Whether the app is installed (standalone) */
  isInstalled: boolean;
  /** Whether the user is online */
  isOnline: boolean;
  /** Whether a new update is available */
  hasUpdate: boolean;
  /** Push notification permission state */
  notificationPermission: NotificationPermission;
  /** Whether push is supported */
  pushSupported: boolean;
}

/**
 * PWA actions interface.
 */
interface PWAActions {
  /** Prompt user to install the PWA */
  promptInstall: () => Promise<boolean>;
  /** Request push notification permission */
  requestNotificationPermission: () => Promise<boolean>;
  /** Subscribe to push notifications */
  subscribeToPush: () => Promise<PushSubscription | null>;
  /** Unsubscribe from push notifications */
  unsubscribeFromPush: () => Promise<boolean>;
  /** Apply pending update */
  applyUpdate: () => void;
  /** Clear all caches */
  clearCache: () => Promise<void>;
}

/**
 * PWA hook return type.
 */
interface UsePWAReturn extends PWAState, PWAActions {}

/**
 * VAPID public key for push notifications.
 * In production, this should come from environment variables.
 */
const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || '';

/**
 * Convert VAPID key to Uint8Array.
 *
 * WHAT: Converts base64 VAPID key for Web Push subscription.
 *
 * WHY: Browser push API requires ArrayBuffer format.
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }

  return outputArray;
}

/**
 * Custom hook for PWA functionality.
 *
 * WHAT: Provides PWA state and actions.
 *
 * WHY: Encapsulates complex PWA logic in reusable hook.
 *
 * HOW: Manages install prompt, notifications, and updates.
 *
 * @returns PWA state and actions
 *
 * @example
 * ```tsx
 * const { canInstall, promptInstall, isOnline } = usePWA();
 *
 * return (
 *   <>
 *     {canInstall && (
 *       <button onClick={promptInstall}>Install App</button>
 *     )}
 *     {!isOnline && <OfflineBanner />}
 *   </>
 * );
 * ```
 */
export function usePWA(): UsePWAReturn {
  // State
  const [canInstall, setCanInstall] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [hasUpdate, setHasUpdate] = useState(false);
  const [notificationPermission, setNotificationPermission] =
    useState<NotificationPermission>('default');
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [swRegistration, setSwRegistration] =
    useState<ServiceWorkerRegistration | null>(null);

  // Check if push is supported
  const pushSupported =
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window;

  // Check if installed (standalone mode)
  useEffect(() => {
    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as any).standalone === true;

    setIsInstalled(isStandalone);
  }, []);

  // Handle beforeinstallprompt event
  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setCanInstall(true);
    };

    window.addEventListener('beforeinstallprompt', handler);

    return () => {
      window.removeEventListener('beforeinstallprompt', handler);
    };
  }, []);

  // Handle app installed event
  useEffect(() => {
    const handler = () => {
      setCanInstall(false);
      setIsInstalled(true);
      setDeferredPrompt(null);
    };

    window.addEventListener('appinstalled', handler);

    return () => {
      window.removeEventListener('appinstalled', handler);
    };
  }, []);

  // Handle online/offline status
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Get service worker registration
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready.then((registration) => {
        setSwRegistration(registration);
      });
    }
  }, []);

  // Check notification permission
  useEffect(() => {
    if ('Notification' in window) {
      setNotificationPermission(Notification.permission);
    }
  }, []);

  // Setup update detection
  useEffect(() => {
    // Expose function for service worker to call
    (window as any).showUpdatePrompt = () => {
      setHasUpdate(true);
    };

    return () => {
      delete (window as any).showUpdatePrompt;
    };
  }, []);

  /**
   * Prompt user to install the PWA.
   *
   * WHAT: Shows browser install prompt.
   *
   * WHY: Allows users to install the app.
   *
   * @returns Whether user accepted the install
   */
  const promptInstall = useCallback(async (): Promise<boolean> => {
    if (!deferredPrompt) {
      return false;
    }

    try {
      await deferredPrompt.prompt();
      const choiceResult = await deferredPrompt.userChoice;

      if (choiceResult.outcome === 'accepted') {
        setCanInstall(false);
        setDeferredPrompt(null);
        return true;
      }

      return false;
    } catch (error) {
      console.error('Install prompt error:', error);
      return false;
    }
  }, [deferredPrompt]);

  /**
   * Request notification permission.
   *
   * WHAT: Asks user for notification permission.
   *
   * WHY: Required before subscribing to push.
   *
   * @returns Whether permission was granted
   */
  const requestNotificationPermission = useCallback(async (): Promise<boolean> => {
    if (!('Notification' in window)) {
      console.warn('Notifications not supported');
      return false;
    }

    try {
      const permission = await Notification.requestPermission();
      setNotificationPermission(permission);
      return permission === 'granted';
    } catch (error) {
      console.error('Notification permission error:', error);
      return false;
    }
  }, []);

  /**
   * Subscribe to push notifications.
   *
   * WHAT: Creates push subscription with server.
   *
   * WHY: Enables receiving push notifications.
   *
   * @returns Push subscription or null
   */
  const subscribeToPush = useCallback(async (): Promise<PushSubscription | null> => {
    if (!swRegistration || !VAPID_PUBLIC_KEY) {
      console.warn('Push not available');
      return null;
    }

    try {
      // Check if already subscribed
      const existingSubscription = await swRegistration.pushManager.getSubscription();
      if (existingSubscription) {
        return existingSubscription;
      }

      // Create new subscription
      const subscription = await swRegistration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });

      // Send subscription to server
      await sendSubscriptionToServer(subscription);

      return subscription;
    } catch (error) {
      console.error('Push subscription error:', error);
      return null;
    }
  }, [swRegistration]);

  /**
   * Unsubscribe from push notifications.
   *
   * WHAT: Removes push subscription.
   *
   * WHY: User may want to stop notifications.
   *
   * @returns Whether unsubscribe succeeded
   */
  const unsubscribeFromPush = useCallback(async (): Promise<boolean> => {
    if (!swRegistration) {
      return false;
    }

    try {
      const subscription = await swRegistration.pushManager.getSubscription();
      if (!subscription) {
        return true;
      }

      // Remove from server
      await removeSubscriptionFromServer(subscription);

      // Unsubscribe locally
      await subscription.unsubscribe();
      return true;
    } catch (error) {
      console.error('Unsubscribe error:', error);
      return false;
    }
  }, [swRegistration]);

  /**
   * Apply pending update.
   *
   * WHAT: Activates new service worker version.
   *
   * WHY: Lets user update to latest version.
   */
  const applyUpdate = useCallback(() => {
    if (swRegistration && swRegistration.waiting) {
      swRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
    }
    setHasUpdate(false);
    window.location.reload();
  }, [swRegistration]);

  /**
   * Clear all caches.
   *
   * WHAT: Removes all cached data.
   *
   * WHY: Useful for troubleshooting or logout.
   */
  const clearCache = useCallback(async (): Promise<void> => {
    if ('caches' in window) {
      const cacheNames = await caches.keys();
      await Promise.all(cacheNames.map((name) => caches.delete(name)));
    }

    if (swRegistration) {
      swRegistration.active?.postMessage({ type: 'CLEAR_CACHE' });
    }
  }, [swRegistration]);

  return {
    // State
    canInstall,
    isInstalled,
    isOnline,
    hasUpdate,
    notificationPermission,
    pushSupported,
    // Actions
    promptInstall,
    requestNotificationPermission,
    subscribeToPush,
    unsubscribeFromPush,
    applyUpdate,
    clearCache,
  };
}

/**
 * Send push subscription to server.
 *
 * WHAT: Registers subscription with backend.
 *
 * WHY: Server needs subscription to send pushes.
 */
async function sendSubscriptionToServer(subscription: PushSubscription): Promise<void> {
  const response = await fetch('/api/push/subscribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(subscription.toJSON()),
  });

  if (!response.ok) {
    throw new Error('Failed to save subscription');
  }
}

/**
 * Remove push subscription from server.
 *
 * WHAT: Unregisters subscription with backend.
 *
 * WHY: Server should stop sending pushes.
 */
async function removeSubscriptionFromServer(
  subscription: PushSubscription
): Promise<void> {
  const response = await fetch('/api/push/unsubscribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ endpoint: subscription.endpoint }),
  });

  if (!response.ok) {
    throw new Error('Failed to remove subscription');
  }
}

export default usePWA;
