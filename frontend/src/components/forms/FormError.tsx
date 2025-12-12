/**
 * FormError Component
 *
 * WHAT: Form-level error alert display.
 *
 * WHY: Standardizes form error display:
 * 1. Consistent styling for error alerts
 * 2. Proper accessibility with role="alert"
 * 3. Conditionally renders only when error exists
 *
 * HOW: Displays error message in styled alert box.
 * Used for API errors and general form errors.
 */

export interface FormErrorProps {
  /** Error message to display */
  error?: string | null;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Form-level error alert component
 */
export function FormError({ error, className = '' }: FormErrorProps) {
  if (!error) return null;

  return (
    <div
      className={`rounded-md bg-red-50 p-4 ${className}`}
      role="alert"
      aria-live="polite"
    >
      <div className="flex">
        <div className="flex-shrink-0">
          <svg
            className="h-5 w-5 text-red-400"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
              clipRule="evenodd"
            />
          </svg>
        </div>
        <div className="ml-3">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      </div>
    </div>
  );
}

export default FormError;
