/**
 * FormField Component
 *
 * WHAT: Reusable form field wrapper with label, input, and error display.
 *
 * WHY: Standardizes form field layout and error handling:
 * 1. Consistent label and input spacing
 * 2. Field-level error messages with proper styling
 * 3. Accessible error association via aria-describedby
 * 4. Support for required field indicators
 *
 * HOW: Wraps children (input) with label and error message.
 * Integrates with react-hook-form error objects.
 */

import type { ReactNode } from 'react';
import type { FieldError } from 'react-hook-form';

export interface FormFieldProps {
  /** Field label text */
  label: string;
  /** HTML name/id for the field */
  name: string;
  /** Whether the field is required */
  required?: boolean;
  /** Error object from react-hook-form */
  error?: FieldError;
  /** Helper text shown below the field */
  helpText?: string;
  /** The input element(s) */
  children: ReactNode;
  /** Additional CSS classes for the container */
  className?: string;
}

/**
 * FormField component for consistent form field layout
 */
export function FormField({
  label,
  name,
  required = false,
  error,
  helpText,
  children,
  className = '',
}: FormFieldProps) {
  const errorId = `${name}-error`;
  const helpId = `${name}-help`;

  return (
    <div className={className}>
      <label
        htmlFor={name}
        className="block text-sm font-medium text-gray-700"
      >
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <div className="mt-1">{children}</div>
      {error && (
        <p
          id={errorId}
          className="mt-1 text-sm text-red-600"
          role="alert"
        >
          {error.message}
        </p>
      )}
      {helpText && !error && (
        <p id={helpId} className="mt-1 text-sm text-gray-500">
          {helpText}
        </p>
      )}
    </div>
  );
}

export default FormField;
