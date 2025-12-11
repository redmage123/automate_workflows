/**
 * Invoice TypeScript Type Definitions
 *
 * WHAT: Type definitions for invoice management features.
 *
 * WHY: Ensures type safety for invoice CRUD operations,
 * payment workflows, and UI components.
 *
 * HOW: Types match the backend Pydantic schemas for consistency.
 */

import type { OrgScopedEntity, InvoiceStatus } from './common';

/**
 * Invoice entity
 *
 * WHAT: Full invoice data as returned by the API.
 *
 * WHY: Includes all fields for invoice display and management.
 */
export interface Invoice extends OrgScopedEntity {
  invoice_number: string;
  status: InvoiceStatus;
  proposal_id: number | null;
  subtotal: number;
  discount_amount: number | null;
  tax_amount: number | null;
  total: number;
  amount_paid: number;
  stripe_payment_intent_id: string | null;
  stripe_checkout_session_id: string | null;
  payment_method: string | null;
  issue_date: string;
  due_date: string | null;
  paid_at: string | null;
  sent_at: string | null;
  notes: string | null;
  is_editable: boolean;
  is_paid: boolean;
  balance_due: number;
}

/**
 * Invoice creation request
 *
 * WHAT: Data required to create a new invoice.
 *
 * WHY: Matches backend InvoiceCreate schema.
 */
export interface InvoiceCreateRequest {
  proposal_id?: number | null;
  subtotal: number;
  discount_amount?: number | null;
  tax_amount?: number | null;
  total: number;
  issue_date?: string | null;
  due_date?: string | null;
  notes?: string | null;
}

/**
 * Invoice update request
 *
 * WHAT: Data for updating an existing invoice.
 *
 * WHY: All fields optional for partial updates. Only DRAFT invoices.
 */
export interface InvoiceUpdateRequest {
  subtotal?: number | null;
  discount_amount?: number | null;
  tax_amount?: number | null;
  total?: number | null;
  due_date?: string | null;
  notes?: string | null;
}

/**
 * Invoice list response
 *
 * WHAT: Paginated list of invoices.
 *
 * WHY: Backend returns skip/limit instead of page/pages.
 */
export interface InvoiceListResponse {
  items: Invoice[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * Invoice statistics
 *
 * WHAT: Aggregated invoice metrics.
 *
 * WHY: Dashboard widgets and financial overview.
 */
export interface InvoiceStats {
  total: number;
  by_status: Record<string, number>;
  total_outstanding: number;
  total_paid: number;
}

/**
 * Invoice list query parameters
 *
 * WHAT: Filters and pagination for invoice list.
 *
 * WHY: Type-safe query building.
 */
export interface InvoiceListParams {
  skip?: number;
  limit?: number;
  status?: InvoiceStatus;
  unpaid_only?: boolean;
}

/**
 * Checkout request
 *
 * WHAT: Data for creating a Stripe Checkout Session.
 *
 * WHY: Provides redirect URLs for payment flow.
 */
export interface CheckoutRequest {
  success_url: string;
  cancel_url: string;
}

/**
 * Checkout response
 *
 * WHAT: Response from checkout session creation.
 *
 * WHY: Provides checkout URL for redirect.
 */
export interface CheckoutResponse {
  checkout_session_id: string;
  checkout_url: string;
}

/**
 * Checkout status response
 *
 * WHAT: Status of a checkout session.
 *
 * WHY: Enables polling for payment completion.
 */
export interface CheckoutStatusResponse {
  session_id: string;
  status: string;
  payment_status: string | null;
}

/**
 * Payment record request
 *
 * WHAT: Data for recording a manual payment.
 *
 * WHY: Supports offline payments (check, bank transfer, cash).
 */
export interface PaymentRecordRequest {
  amount: number;
  payment_method?: string;
}

/**
 * Status display configuration
 *
 * WHAT: UI metadata for invoice statuses.
 *
 * WHY: Consistent status badges and colors.
 */
export const INVOICE_STATUS_CONFIG: Record<
  InvoiceStatus,
  { label: string; color: string; bgColor: string }
> = {
  draft: { label: 'Draft', color: 'text-gray-600', bgColor: 'bg-gray-100' },
  sent: { label: 'Sent', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  paid: { label: 'Paid', color: 'text-green-600', bgColor: 'bg-green-100' },
  partially_paid: { label: 'Partially Paid', color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  overdue: { label: 'Overdue', color: 'text-red-600', bgColor: 'bg-red-100' },
  cancelled: { label: 'Cancelled', color: 'text-gray-500', bgColor: 'bg-gray-100' },
  refunded: { label: 'Refunded', color: 'text-purple-600', bgColor: 'bg-purple-100' },
};

/**
 * Format currency for display
 *
 * WHAT: Formats a number as USD currency.
 *
 * WHY: Consistent money formatting across the app.
 *
 * Note: This function is also exported from proposal.ts. When importing
 * from types/index.ts, use the one from proposal. Import from this file
 * directly for invoice-specific usage.
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}
