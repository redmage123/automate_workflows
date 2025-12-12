/**
 * SubmitButton Component
 *
 * WHAT: Form submit button with loading state.
 *
 * WHY: Standardizes submit button behavior:
 * 1. Consistent loading spinner
 * 2. Disabled state during submission
 * 3. Custom loading text support
 * 4. Accessible loading announcement
 *
 * HOW: Button that shows spinner when loading prop is true.
 * Disables during loading to prevent double submission.
 */

import type { ButtonHTMLAttributes, ReactNode } from 'react';

export interface SubmitButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Whether the form is submitting */
  isLoading?: boolean;
  /** Text to show while loading */
  loadingText?: string;
  /** Button content */
  children: ReactNode;
  /** Button variant */
  variant?: 'primary' | 'secondary' | 'danger';
  /** Full width button */
  fullWidth?: boolean;
}

/**
 * Submit button with loading state
 */
export function SubmitButton({
  isLoading = false,
  loadingText = 'Saving...',
  children,
  variant = 'primary',
  fullWidth = false,
  className = '',
  disabled,
  ...props
}: SubmitButtonProps) {
  const variantClasses = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    danger: 'btn-danger',
  };

  return (
    <button
      type="submit"
      disabled={isLoading || disabled}
      className={`${variantClasses[variant]} ${fullWidth ? 'w-full' : ''} ${className}`}
      aria-busy={isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="flex items-center justify-center">
          <svg
            className="animate-spin -ml-1 mr-3 h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
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
          {loadingText}
        </span>
      ) : (
        children
      )}
    </button>
  );
}

export default SubmitButton;
