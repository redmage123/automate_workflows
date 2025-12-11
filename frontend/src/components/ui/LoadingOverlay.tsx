/**
 * Loading Overlay Component
 *
 * WHAT: Full-screen or container overlay for loading states.
 *
 * WHY: Blocks interaction during async operations.
 *
 * HOW: Semi-transparent backdrop with centered spinner.
 */

import LoadingSpinner from './LoadingSpinner';

interface LoadingOverlayProps {
  message?: string;
  fullScreen?: boolean;
}

function LoadingOverlay({ message, fullScreen = false }: LoadingOverlayProps) {
  const containerClass = fullScreen
    ? 'fixed inset-0 z-50'
    : 'absolute inset-0 z-10';

  return (
    <div
      className={`${containerClass} flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm`}
    >
      <LoadingSpinner size="lg" />
      {message && (
        <p className="mt-4 text-sm font-medium text-gray-600">{message}</p>
      )}
    </div>
  );
}

export default LoadingOverlay;
