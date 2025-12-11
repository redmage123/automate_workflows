/**
 * Type Definitions Index
 *
 * WHAT: Central export point for all TypeScript type definitions.
 *
 * WHY: Single import path simplifies usage across components
 * and ensures consistent access to all types.
 *
 * HOW: Re-exports all types from individual modules.
 */

export * from './common';
export * from './auth';
export * from './project';
export * from './proposal';
export * from './workflow';
export * from './ticket';
// Exclude formatCurrency from invoice to avoid duplicate export with proposal
export {
  type Invoice,
  type InvoiceCreateRequest,
  type InvoiceUpdateRequest,
  type InvoiceListResponse,
  type InvoiceStats,
  type InvoiceListParams,
  type CheckoutRequest,
  type CheckoutResponse,
  type CheckoutStatusResponse,
  type PaymentRecordRequest,
  INVOICE_STATUS_CONFIG,
} from './invoice';
