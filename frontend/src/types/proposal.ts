/**
 * Proposal TypeScript Type Definitions
 *
 * WHAT: Type definitions for proposal management features.
 *
 * WHY: Ensures type safety for proposal CRUD operations,
 * approval workflow, and UI components.
 *
 * HOW: Types match the backend Pydantic schemas for consistency.
 */

import type { OrgScopedEntity, ProposalStatus } from './common';

/**
 * Line item in a proposal
 *
 * WHAT: Individual pricing item with quantity and unit price.
 *
 * WHY: Enables itemized pricing and automatic total calculation.
 */
export interface LineItem {
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
}

/**
 * Proposal entity
 *
 * WHAT: Full proposal data as returned by the API.
 *
 * WHY: Includes all fields for proposal display and management.
 */
export interface Proposal extends OrgScopedEntity {
  title: string;
  description: string | null;
  status: ProposalStatus;
  project_id: number;
  version: number;
  previous_version_id: number | null;
  line_items: LineItem[] | null;
  subtotal: number;
  discount_percent: number | null;
  discount_amount: number | null;
  tax_percent: number | null;
  tax_amount: number | null;
  total: number;
  valid_until: string | null;
  sent_at: string | null;
  viewed_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  notes: string | null; // Internal notes (ADMIN only)
  client_notes: string | null;
  terms: string | null;
  is_editable: boolean;
  is_expired: boolean;
  can_be_approved: boolean;
}

/**
 * Proposal creation request
 *
 * WHAT: Data required to create a new proposal.
 *
 * WHY: Matches backend ProposalCreate schema.
 */
export interface ProposalCreateRequest {
  title: string;
  description?: string | null;
  project_id: number;
  line_items?: LineItem[] | null;
  discount_percent?: number | null;
  tax_percent?: number | null;
  valid_until?: string | null;
  notes?: string | null;
  client_notes?: string | null;
  terms?: string | null;
}

/**
 * Proposal update request
 *
 * WHAT: Data for updating an existing proposal.
 *
 * WHY: All fields optional for partial updates. Only DRAFT proposals.
 */
export interface ProposalUpdateRequest {
  title?: string;
  description?: string | null;
  line_items?: LineItem[] | null;
  discount_percent?: number | null;
  tax_percent?: number | null;
  valid_until?: string | null;
  notes?: string | null;
  client_notes?: string | null;
  terms?: string | null;
}

/**
 * Proposal rejection request
 *
 * WHAT: Data for rejecting a proposal.
 *
 * WHY: Captures reason for analytics and follow-up.
 */
export interface ProposalRejectRequest {
  reason?: string | null;
}

/**
 * Proposal revision request
 *
 * WHAT: Data for creating a revised proposal version.
 *
 * WHY: Preserves original while creating new version.
 */
export interface ProposalReviseRequest {
  title?: string;
  description?: string | null;
  line_items?: LineItem[] | null;
  discount_percent?: number | null;
  tax_percent?: number | null;
  valid_until?: string | null;
  notes?: string | null;
  client_notes?: string | null;
  terms?: string | null;
}

/**
 * Proposal list response
 *
 * WHAT: Paginated list of proposals.
 *
 * WHY: Backend returns skip/limit instead of page/pages.
 */
export interface ProposalListResponse {
  items: Proposal[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * Proposal statistics
 *
 * WHAT: Aggregated proposal metrics.
 *
 * WHY: Dashboard widgets and pipeline overview.
 */
export interface ProposalStats {
  total: number;
  by_status: Record<string, number>;
  pending_count: number;
  total_value: number;
  approved_value: number;
}

/**
 * Proposal list query parameters
 *
 * WHAT: Filters and pagination for proposal list.
 *
 * WHY: Type-safe query building.
 */
export interface ProposalListParams {
  skip?: number;
  limit?: number;
  status?: ProposalStatus;
  project_id?: number;
  pending_only?: boolean;
}

/**
 * Status display configuration
 *
 * WHAT: UI metadata for proposal statuses.
 *
 * WHY: Consistent status badges and colors.
 */
export const PROPOSAL_STATUS_CONFIG: Record<
  ProposalStatus,
  { label: string; color: string; bgColor: string }
> = {
  draft: { label: 'Draft', color: 'text-gray-600', bgColor: 'bg-gray-100' },
  sent: { label: 'Sent', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  viewed: { label: 'Viewed', color: 'text-purple-600', bgColor: 'bg-purple-100' },
  approved: { label: 'Approved', color: 'text-green-600', bgColor: 'bg-green-100' },
  rejected: { label: 'Rejected', color: 'text-red-600', bgColor: 'bg-red-100' },
  expired: { label: 'Expired', color: 'text-orange-600', bgColor: 'bg-orange-100' },
  revised: { label: 'Revised', color: 'text-indigo-600', bgColor: 'bg-indigo-100' },
};

/**
 * Format currency for display
 *
 * WHAT: Formats a number as USD currency.
 *
 * WHY: Consistent money formatting across the app.
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}
