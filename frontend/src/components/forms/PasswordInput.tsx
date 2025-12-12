/**
 * PasswordInput Component
 *
 * WHAT: Password input with visibility toggle (eye icon).
 *
 * WHY: Improves UX by allowing users to:
 * 1. See what they're typing to avoid mistakes
 * 2. Verify password before submission
 * 3. Toggle visibility on/off as needed
 *
 * HOW: Wraps standard input with a toggle button that switches
 * between type="password" and type="text". Uses forwardRef for
 * react-hook-form compatibility.
 */

import { forwardRef, useState, type InputHTMLAttributes } from 'react';

export interface PasswordInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  /** Whether the input has an error */
  error?: boolean;
  /** ID of the error message element for aria-describedby */
  errorId?: string;
}

/**
 * Password input with visibility toggle
 */
export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ error, errorId, className = '', ...props }, ref) => {
    const [showPassword, setShowPassword] = useState(false);

    const baseClasses = `block w-full rounded-md px-3 py-2 pr-10 shadow-sm sm:text-sm
      focus:outline-none focus:ring-1`;

    const normalClasses = `border border-gray-300
      focus:border-primary-500 focus:ring-primary-500`;

    const errorClasses = `border border-red-300
      focus:border-red-500 focus:ring-red-500`;

    return (
      <div className="relative">
        <input
          ref={ref}
          type={showPassword ? 'text' : 'password'}
          className={`${baseClasses} ${error ? errorClasses : normalClasses} ${className}`}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error && errorId ? errorId : undefined}
          {...props}
        />
        <button
          type="button"
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600"
          onClick={() => setShowPassword(!showPassword)}
          aria-label={showPassword ? 'Hide password' : 'Show password'}
          tabIndex={-1}
        >
          {showPassword ? (
            // Eye-off icon (password visible, click to hide)
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
              />
            </svg>
          ) : (
            // Eye icon (password hidden, click to show)
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
              />
            </svg>
          )}
        </button>
      </div>
    );
  }
);

PasswordInput.displayName = 'PasswordInput';

export default PasswordInput;
