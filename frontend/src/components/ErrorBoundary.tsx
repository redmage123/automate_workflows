/**
 * Error Boundary Component
 *
 * WHAT: Catches JavaScript errors in child component tree.
 *
 * WHY: Prevents entire app from crashing on unexpected errors.
 * Instead, displays a fallback UI with error information.
 *
 * HOW: Uses React class component error boundary lifecycle methods.
 * Must be a class component as hooks cannot catch rendering errors.
 */

import { Component, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  /**
   * Update state when error occurs.
   *
   * WHY: This lifecycle method allows the component to render
   * a fallback UI after an error is thrown.
   */
  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  /**
   * Log error information.
   *
   * WHY: Captures detailed error info for debugging.
   * In production, this could send to error tracking service.
   */
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    this.setState({ errorInfo });
    // In production, send to error tracking service
    console.error('ErrorBoundary caught error:', error, errorInfo);
  }

  /**
   * Reset error state to retry rendering.
   */
  handleRetry = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <div className="flex min-h-screen flex-col items-center justify-center px-4">
          <div className="text-center max-w-lg">
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
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>

            <h1 className="mt-6 text-3xl font-bold tracking-tight text-gray-900">
              Something went wrong
            </h1>
            <p className="mt-4 text-base text-gray-600">
              An unexpected error occurred. Our team has been notified.
            </p>

            {/* Error details in development */}
            {import.meta.env.DEV && this.state.error && (
              <div className="mt-6 text-left">
                <details className="bg-gray-50 rounded-lg p-4">
                  <summary className="cursor-pointer text-sm font-medium text-gray-700">
                    Error details (development only)
                  </summary>
                  <div className="mt-4">
                    <p className="text-sm font-mono text-red-600 break-all">
                      {this.state.error.toString()}
                    </p>
                    {this.state.errorInfo && (
                      <pre className="mt-2 text-xs text-gray-600 overflow-auto max-h-48">
                        {this.state.errorInfo.componentStack}
                      </pre>
                    )}
                  </div>
                </details>
              </div>
            )}

            <div className="mt-10 flex items-center justify-center gap-x-6">
              <button onClick={this.handleRetry} className="btn-primary">
                Try again
              </button>
              <Link to="/dashboard" className="text-sm font-semibold text-gray-900">
                Go to dashboard <span aria-hidden="true">&rarr;</span>
              </Link>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
