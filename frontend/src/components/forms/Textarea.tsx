/**
 * Textarea Component
 *
 * WHAT: Styled textarea with error state support.
 *
 * WHY: Standardizes textarea styling and behavior:
 * 1. Consistent look across all forms
 * 2. Automatic error styling when error prop is present
 * 3. Proper accessibility attributes
 * 4. Works with react-hook-form register
 *
 * HOW: Extends native textarea with custom styling and error state.
 * Uses forwardRef for react-hook-form compatibility.
 */

import { forwardRef, type TextareaHTMLAttributes } from 'react';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** Whether the textarea has an error */
  error?: boolean;
  /** ID of the error message element for aria-describedby */
  errorId?: string;
}

/**
 * Styled textarea component with error state
 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ error, errorId, className = '', ...props }, ref) => {
    const baseClasses = `block w-full rounded-md px-3 py-2 shadow-sm sm:text-sm
      focus:outline-none focus:ring-1`;

    const normalClasses = `border border-gray-300
      focus:border-primary-500 focus:ring-primary-500`;

    const errorClasses = `border border-red-300
      focus:border-red-500 focus:ring-red-500`;

    return (
      <textarea
        ref={ref}
        className={`${baseClasses} ${error ? errorClasses : normalClasses} ${className}`}
        aria-invalid={error ? 'true' : 'false'}
        aria-describedby={error && errorId ? errorId : undefined}
        {...props}
      />
    );
  }
);

Textarea.displayName = 'Textarea';

export default Textarea;
