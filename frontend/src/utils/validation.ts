/**
 * Form Validation Utilities
 *
 * WHAT: Zod schemas and validation utilities for form data.
 *
 * WHY: Centralized validation logic provides:
 * 1. Type-safe form data with inference
 * 2. Consistent validation rules across the app
 * 3. Reusable schemas for common patterns
 * 4. Integration with react-hook-form via @hookform/resolvers
 *
 * HOW: Export Zod schemas that can be used with zodResolver
 * in react-hook-form. Schemas define field requirements, types,
 * and custom validation messages.
 */

import { z } from 'zod';

// ============================================================================
// Common Validation Patterns
// ============================================================================

/**
 * Email validation pattern
 * WHY: Standard email format validation with clear error message
 */
export const emailSchema = z
  .string()
  .min(1, 'Email is required')
  .email('Please enter a valid email address');

/**
 * Password validation pattern
 * WHY: Enforces minimum security requirements
 */
export const passwordSchema = z
  .string()
  .min(1, 'Password is required')
  .min(8, 'Password must be at least 8 characters');

/**
 * Strong password validation
 * WHY: For registration, enforce stronger requirements
 */
export const strongPasswordSchema = z
  .string()
  .min(1, 'Password is required')
  .min(8, 'Password must be at least 8 characters')
  .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
  .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
  .regex(/[0-9]/, 'Password must contain at least one number');

/**
 * Required string pattern
 * WHY: Simple required field validation
 */
export const requiredString = (fieldName: string) =>
  z.string().min(1, `${fieldName} is required`);

/**
 * Optional string that can be empty
 * WHY: For optional text fields
 */
export const optionalString = z.string().optional().or(z.literal(''));

/**
 * Positive number validation
 * WHY: For price, quantity, and other numeric fields
 */
export const positiveNumber = (fieldName: string) =>
  z.number({ invalid_type_error: `${fieldName} must be a number` })
    .positive(`${fieldName} must be greater than 0`);

/**
 * Non-negative number validation
 * WHY: For fields that can be zero (discount, etc.)
 */
export const nonNegativeNumber = (fieldName: string) =>
  z.number({ invalid_type_error: `${fieldName} must be a number` })
    .min(0, `${fieldName} cannot be negative`);

// ============================================================================
// Authentication Schemas
// ============================================================================

/**
 * Login form schema
 */
export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, 'Password is required'),
});

export type LoginFormData = z.infer<typeof loginSchema>;

/**
 * Registration form schema
 * WHY: Matches backend RegisterRequest schema requirements
 */
export const registerSchema = z
  .object({
    name: z
      .string()
      .min(1, 'Full name is required')
      .max(255, 'Name must be less than 255 characters'),
    organization_name: z
      .string()
      .min(1, 'Organization name is required')
      .min(2, 'Organization name must be at least 2 characters')
      .max(100, 'Organization name must be less than 100 characters'),
    email: emailSchema,
    password: strongPasswordSchema,
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

export type RegisterFormData = z.infer<typeof registerSchema>;

/**
 * Forgot password form schema
 */
export const forgotPasswordSchema = z.object({
  email: emailSchema,
});

export type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;

/**
 * Reset password form schema
 */
export const resetPasswordSchema = z
  .object({
    password: strongPasswordSchema,
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

export type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>;

// ============================================================================
// Project Schemas
// ============================================================================

/**
 * Project priority enum values (lowercase to match backend)
 */
export const projectPrioritySchema = z.enum(['low', 'medium', 'high', 'urgent'], {
  errorMap: () => ({ message: 'Please select a priority' }),
});

/**
 * Create/Edit project form schema
 *
 * WHY: String types for hours/dates to match HTML input behavior.
 * Numeric validation done via transform or at submission time.
 */
export const projectSchema = z.object({
  name: z
    .string()
    .min(1, 'Project name is required')
    .max(255, 'Project name must be less than 255 characters'),
  description: optionalString,
  priority: projectPrioritySchema,
  estimatedHours: z.string().optional(),
  actualHours: z.string().optional(),
  startDate: z.string().optional(),
  dueDate: z.string().optional(),
}).refine(
  (data) => {
    if (data.startDate && data.dueDate) {
      return new Date(data.dueDate) >= new Date(data.startDate);
    }
    return true;
  },
  {
    message: 'Due date must be after or equal to start date',
    path: ['dueDate'],
  }
);

export type ProjectFormData = z.infer<typeof projectSchema>;

// ============================================================================
// Proposal Schemas
// ============================================================================

/**
 * Line item schema for proposals
 */
export const lineItemSchema = z.object({
  description: z.string().min(1, 'Description is required'),
  quantity: z
    .number({ invalid_type_error: 'Quantity must be a number' })
    .positive('Quantity must be greater than 0'),
  unitPrice: z
    .number({ invalid_type_error: 'Unit price must be a number' })
    .min(0, 'Unit price cannot be negative'),
});

export type LineItemFormData = z.infer<typeof lineItemSchema>;

/**
 * Create/Edit proposal form schema
 */
export const proposalSchema = z.object({
  title: z
    .string()
    .min(1, 'Title is required')
    .max(200, 'Title must be less than 200 characters'),
  description: optionalString,
  projectId: z.union([
    z.number().positive('Please select a project'),
    z.literal(''),
  ]),
  lineItems: z
    .array(lineItemSchema)
    .min(1, 'At least one line item is required'),
  discountPercent: nonNegativeNumber('Discount'),
  taxPercent: nonNegativeNumber('Tax'),
  validUntil: z.string().optional().nullable(),
  notes: optionalString,
  clientNotes: optionalString,
  terms: optionalString,
});

export type ProposalFormData = z.infer<typeof proposalSchema>;

// ============================================================================
// Ticket Schemas
// ============================================================================

/**
 * Ticket priority enum values (lowercase to match backend)
 */
export const ticketPrioritySchema = z.enum(['low', 'medium', 'high', 'urgent'], {
  errorMap: () => ({ message: 'Please select a priority' }),
});

/**
 * Ticket category enum values (lowercase to match backend)
 */
export const ticketCategorySchema = z.enum(['general', 'bug', 'feature', 'question', 'support'], {
  errorMap: () => ({ message: 'Please select a category' }),
});

/**
 * Create/Edit ticket form schema
 */
export const ticketSchema = z.object({
  subject: z
    .string()
    .min(1, 'Subject is required')
    .max(255, 'Subject must be less than 255 characters'),
  description: z
    .string()
    .min(1, 'Description is required')
    .min(10, 'Description must be at least 10 characters'),
  priority: ticketPrioritySchema,
  category: ticketCategorySchema,
  projectId: z.string().optional(),
});

export type TicketFormData = z.infer<typeof ticketSchema>;

// ============================================================================
// Organization Schemas
// ============================================================================

/**
 * Organization settings form schema
 */
export const organizationSettingsSchema = z.object({
  name: z
    .string()
    .min(1, 'Organization name is required')
    .min(2, 'Organization name must be at least 2 characters')
    .max(100, 'Organization name must be less than 100 characters'),
  description: optionalString,
});

export type OrganizationSettingsFormData = z.infer<typeof organizationSettingsSchema>;

// ============================================================================
// User Schemas
// ============================================================================

/**
 * User profile update schema
 */
export const userProfileSchema = z.object({
  name: z
    .string()
    .min(1, 'Name is required')
    .max(100, 'Name must be less than 100 characters'),
  email: emailSchema,
});

export type UserProfileFormData = z.infer<typeof userProfileSchema>;

/**
 * Change password schema
 */
export const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, 'Current password is required'),
    newPassword: strongPasswordSchema,
    confirmPassword: z.string().min(1, 'Please confirm your new password'),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

export type ChangePasswordFormData = z.infer<typeof changePasswordSchema>;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Parse numeric input from string
 * WHY: HTML inputs return strings, need to convert to numbers
 */
export function parseNumericInput(value: string): number | undefined {
  const parsed = parseFloat(value);
  return isNaN(parsed) ? undefined : parsed;
}

/**
 * Format validation error for display
 * WHY: Standardize error message formatting
 */
export function formatValidationError(error: z.ZodError): string {
  return error.errors.map((e) => e.message).join('. ');
}
