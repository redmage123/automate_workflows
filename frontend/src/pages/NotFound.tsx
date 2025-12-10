/**
 * Not Found (404) Page Component
 *
 * WHAT: Error page displayed when route doesn't exist.
 *
 * WHY: Provides friendly error message and navigation back to valid routes.
 *
 * HOW: Simple centered layout with error message and link to home.
 */

import { Link } from 'react-router-dom';

function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="text-center">
        <p className="text-base font-semibold text-primary-600">404</p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          Page not found
        </h1>
        <p className="mt-6 text-base text-gray-600">
          Sorry, we couldn't find the page you're looking for.
        </p>
        <div className="mt-10 flex items-center justify-center gap-x-6">
          <Link to="/dashboard" className="btn-primary">
            Go back home
          </Link>
          <Link to="/tickets" className="text-sm font-semibold text-gray-900">
            Contact support <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default NotFound;
