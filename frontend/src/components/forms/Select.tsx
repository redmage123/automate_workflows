/**
 * Select Component
 *
 * WHAT: Styled select dropdown with error state support.
 *
 * WHY: Standardizes select styling and behavior:
 * 1. Consistent look across all forms
 * 2. Automatic error styling when error prop is present
 * 3. Proper accessibility attributes
 * 4. Works with react-hook-form register
 *
 * HOW: Extends native select with custom styling and error state.
 * Uses forwardRef for react-hook-form compatibility.
 */

import { forwardRef, type SelectHTMLAttributes, type ReactNode } from 'react';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** Whether the select has an error */
  error?: boolean;
  /** ID of the error message element for aria-describedby */
  errorId?: string;
  /** Select options */
  children: ReactNode;
}

/**
 * Styled select component with error state
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ error, errorId, className = '', children, ...props }, ref) => {
    const baseClasses = `block w-full rounded-md px-3 py-2 shadow-sm sm:text-sm
      focus:outline-none focus:ring-1`;

    const normalClasses = `border border-gray-300
      focus:border-primary-500 focus:ring-primary-500`;

    const errorClasses = `border border-red-300
      focus:border-red-500 focus:ring-red-500`;

    return (
      <select
        ref={ref}
        className={`${baseClasses} ${error ? errorClasses : normalClasses} ${className}`}
        aria-invalid={error ? 'true' : 'false'}
        aria-describedby={error && errorId ? errorId : undefined}
        {...props}
      >
        {children}
      </select>
    );
  }
);

Select.displayName = 'Select';

export default Select;
