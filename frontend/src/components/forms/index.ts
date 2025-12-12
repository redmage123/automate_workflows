/**
 * Form Components Index
 *
 * WHAT: Re-exports all form components for easier imports.
 *
 * WHY: Allows importing multiple components from a single path:
 * import { FormField, Input, FormError } from '@/components/forms';
 */

export { FormField } from './FormField';
export type { FormFieldProps } from './FormField';

export { Input } from './Input';
export type { InputProps } from './Input';

export { PasswordInput } from './PasswordInput';
export type { PasswordInputProps } from './PasswordInput';

export { Select } from './Select';
export type { SelectProps } from './Select';

export { Textarea } from './Textarea';
export type { TextareaProps } from './Textarea';

export { FormError } from './FormError';
export type { FormErrorProps } from './FormError';

export { SubmitButton } from './SubmitButton';
export type { SubmitButtonProps } from './SubmitButton';
