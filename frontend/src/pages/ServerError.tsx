/**
 * Server Error (500) Page Component
 *
 * WHAT: Error page displayed when server-side error occurs.
 *
 * WHY: Provides friendly error message when API calls fail unexpectedly.
 *
 * HOW: Simple centered layout with error message and retry option.
 */

import { Link } from 'react-router-dom';

interface ServerErrorProps {
  message?: string;
  onRetry?: () => void;
}

function ServerError({ message, onRetry }: ServerErrorProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="text-center">
        {/* Error icon */}
        <div className="mx-auto h-16 w-16 text-red-500">
          <svg
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            className="h-full w-full"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        <p className="mt-4 text-base font-semibold text-red-600">500</p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          Server error
        </h1>
        <p className="mt-6 text-base text-gray-600">
          {message || "Something went wrong on our end. Please try again later."}
        </p>
        <div className="mt-10 flex items-center justify-center gap-x-6">
          {onRetry ? (
            <button onClick={onRetry} className="btn-primary">
              Try again
            </button>
          ) : (
            <Link to="/dashboard" className="btn-primary">
              Go back home
            </Link>
          )}
          <Link to="/tickets/new" className="text-sm font-semibold text-gray-900">
            Report issue <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default ServerError;
