/**
 * Invoice API Service
 *
 * WHAT: API client functions for invoice management and payment workflows.
 *
 * WHY: Encapsulates all invoice-related API calls including:
 * - CRUD operations
 * - Payment workflow (send, cancel, record payment)
 * - Stripe checkout integration
 * - PDF download
 *
 * HOW: Uses the base API client with typed request/response functions.
 */

import { api, apiGet, apiPost, apiPatch, apiDelete } from './api';
import type {
  Invoice,
  InvoiceCreateRequest,
  InvoiceUpdateRequest,
  InvoiceListResponse,
  InvoiceStats,
  InvoiceListParams,
  CheckoutRequest,
  CheckoutResponse,
  CheckoutStatusResponse,
  PaymentRecordRequest,
} from '../types';

/**
 * Build query string from params object
 *
 * WHAT: Converts params object to URL query string.
 *
 * WHY: Filters out undefined values and properly encodes params.
 */
function buildQueryString(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value));
    }
  });
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : '';
}

// =============================================================================
// Invoice CRUD Operations
// =============================================================================

/**
 * Get paginated list of invoices
 *
 * WHAT: Fetches invoices with optional filters and pagination.
 *
 * WHY: Main method for invoice list views with filtering.
 *
 * @param params - Filter and pagination options
 * @returns Paginated invoice list
 */
export async function getInvoices(params: InvoiceListParams = {}): Promise<InvoiceListResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiGet<InvoiceListResponse>(`/api/invoices${queryString}`);
}

/**
 * Get single invoice by ID
 *
 * WHAT: Fetches full invoice details.
 *
 * WHY: Used for invoice detail views and payment pages.
 *
 * @param id - Invoice ID
 * @returns Invoice data
 */
export async function getInvoice(id: number): Promise<Invoice> {
  return apiGet<Invoice>(`/api/invoices/${id}`);
}

/**
 * Create new invoice
 *
 * WHAT: Creates an invoice in DRAFT status.
 *
 * WHY: ADMINs create invoices for custom billing.
 * Note: Most invoices are auto-created from approved proposals.
 *
 * @param data - Invoice creation data
 * @returns Created invoice
 */
export async function createInvoice(data: InvoiceCreateRequest): Promise<Invoice> {
  return apiPost<Invoice>('/api/invoices', data);
}

/**
 * Update invoice details
 *
 * WHAT: Updates invoice fields.
 *
 * WHY: Modify invoice before sending.
 * Note: Only DRAFT invoices can be updated.
 *
 * @param id - Invoice ID
 * @param data - Update data (partial)
 * @returns Updated invoice
 */
export async function updateInvoice(id: number, data: InvoiceUpdateRequest): Promise<Invoice> {
  return apiPatch<Invoice>(`/api/invoices/${id}`, data);
}

/**
 * Delete invoice
 *
 * WHAT: Permanently removes an invoice.
 *
 * WHY: Cleanup of draft invoices no longer needed.
 * Note: Only DRAFT invoices can be deleted.
 *
 * @param id - Invoice ID
 */
export async function deleteInvoice(id: number): Promise<void> {
  return apiDelete(`/api/invoices/${id}`);
}

/**
 * Get invoice statistics
 *
 * WHAT: Fetches aggregated invoice metrics.
 *
 * WHY: Dashboard widgets and financial overview.
 *
 * @returns Invoice statistics
 */
export async function getInvoiceStats(): Promise<InvoiceStats> {
  return apiGet<InvoiceStats>('/api/invoices/stats');
}

// =============================================================================
// Invoice Workflow Operations
// =============================================================================

/**
 * Send invoice to client
 *
 * WHAT: Transitions invoice from DRAFT to SENT.
 *
 * WHY: Makes invoice payable and records sent_at timestamp.
 *
 * @param id - Invoice ID
 * @returns Updated invoice
 */
export async function sendInvoice(id: number): Promise<Invoice> {
  return apiPost<Invoice>(`/api/invoices/${id}/send`);
}

/**
 * Cancel invoice
 *
 * WHAT: Transitions invoice to CANCELLED status.
 *
 * WHY: Cancel invoices created in error or no longer needed.
 * Note: Paid or refunded invoices cannot be cancelled.
 *
 * @param id - Invoice ID
 * @param reason - Optional cancellation reason
 * @returns Updated invoice
 */
export async function cancelInvoice(id: number, reason?: string): Promise<Invoice> {
  const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
  return apiPost<Invoice>(`/api/invoices/${id}/cancel${params}`);
}

/**
 * Record manual payment
 *
 * WHAT: Records payment received outside Stripe.
 *
 * WHY: Supports offline payments (check, bank transfer, cash).
 *
 * @param id - Invoice ID
 * @param data - Payment details
 * @returns Updated invoice
 */
export async function recordPayment(id: number, data: PaymentRecordRequest): Promise<Invoice> {
  return apiPost<Invoice>(`/api/invoices/${id}/record-payment`, data);
}

// =============================================================================
// Stripe Payment Operations
// =============================================================================

/**
 * Create checkout session
 *
 * WHAT: Creates a Stripe Checkout Session for invoice payment.
 *
 * WHY: Enables PCI-compliant payment collection.
 *
 * @param invoiceId - Invoice ID
 * @param data - Checkout configuration with redirect URLs
 * @returns Checkout session with redirect URL
 */
export async function createCheckoutSession(
  invoiceId: number,
  data: CheckoutRequest
): Promise<CheckoutResponse> {
  return apiPost<CheckoutResponse>(`/api/payments/checkout?invoice_id=${invoiceId}`, data);
}

/**
 * Get checkout session status
 *
 * WHAT: Retrieves current status of a checkout session.
 *
 * WHY: Enables polling for payment completion.
 *
 * @param sessionId - Stripe Checkout Session ID
 * @returns Checkout session status
 */
export async function getCheckoutStatus(sessionId: string): Promise<CheckoutStatusResponse> {
  return apiGet<CheckoutStatusResponse>(`/api/payments/checkout/${sessionId}/status`);
}

// =============================================================================
// PDF Operations
// =============================================================================

/**
 * Download invoice PDF
 *
 * WHAT: Downloads invoice as PDF file.
 *
 * WHY: Professional document for sharing and record keeping.
 *
 * @param id - Invoice ID
 * @returns Blob containing PDF data
 */
export async function downloadInvoicePdf(id: number): Promise<Blob> {
  const response = await api.get(`/api/invoices/${id}/pdf`, {
    responseType: 'blob',
  });
  return response.data;
}

/**
 * Open invoice PDF in new tab
 *
 * WHAT: Downloads and opens PDF in new browser tab.
 *
 * WHY: Quick preview without downloading to filesystem.
 *
 * @param id - Invoice ID
 */
export async function openInvoicePdf(id: number): Promise<void> {
  const blob = await downloadInvoicePdf(id);
  const url = window.URL.createObjectURL(blob);
  window.open(url, '_blank');
  // Clean up the URL after a short delay
  setTimeout(() => window.URL.revokeObjectURL(url), 1000);
}

/**
 * Save invoice PDF to filesystem
 *
 * WHAT: Downloads PDF and triggers browser download.
 *
 * WHY: Save invoice to local filesystem.
 *
 * @param id - Invoice ID
 * @param invoiceNumber - Invoice number for filename
 */
export async function saveInvoicePdf(id: number, invoiceNumber: string): Promise<void> {
  const blob = await downloadInvoicePdf(id);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `invoice-${invoiceNumber}.pdf`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get unpaid invoices
 *
 * WHAT: Fetches invoices with outstanding balance.
 *
 * WHY: Shortcut for filtering unpaid invoices.
 *
 * @param params - Optional pagination
 * @returns Unpaid invoices
 */
export async function getUnpaidInvoices(
  params: Omit<InvoiceListParams, 'unpaid_only'> = {}
): Promise<InvoiceListResponse> {
  return getInvoices({ ...params, unpaid_only: true });
}
