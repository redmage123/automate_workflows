/**
 * Proposal API Service
 *
 * WHAT: API client functions for proposal management and workflow operations.
 *
 * WHY: Encapsulates all proposal-related API calls including:
 * - CRUD operations
 * - Approval workflow (send, view, approve, reject)
 * - Revision management
 *
 * HOW: Uses the base API client with typed request/response functions.
 */

import { apiGet, apiPost, apiPut, apiDelete } from './api';
import type {
  Proposal,
  ProposalCreateRequest,
  ProposalUpdateRequest,
  ProposalRejectRequest,
  ProposalReviseRequest,
  ProposalListResponse,
  ProposalStats,
  ProposalListParams,
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

/**
 * Get paginated list of proposals
 *
 * WHAT: Fetches proposals with optional filters and pagination.
 *
 * WHY: Main method for proposal list views with filtering.
 *
 * @param params - Filter and pagination options
 * @returns Paginated proposal list
 */
export async function getProposals(params: ProposalListParams = {}): Promise<ProposalListResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiGet<ProposalListResponse>(`/api/proposals${queryString}`);
}

/**
 * Get single proposal by ID
 *
 * WHAT: Fetches full proposal details.
 *
 * WHY: Used for proposal detail views and editing.
 * Note: Internal notes only visible to ADMINs.
 *
 * @param id - Proposal ID
 * @returns Proposal data
 */
export async function getProposal(id: number): Promise<Proposal> {
  return apiGet<Proposal>(`/api/proposals/${id}`);
}

/**
 * Create new proposal
 *
 * WHAT: Creates a proposal in DRAFT status.
 *
 * WHY: ADMINs create proposals for client projects.
 * Totals are automatically calculated from line items.
 *
 * @param data - Proposal creation data
 * @returns Created proposal
 */
export async function createProposal(data: ProposalCreateRequest): Promise<Proposal> {
  return apiPost<Proposal>('/api/proposals', data);
}

/**
 * Update proposal details
 *
 * WHAT: Updates proposal fields.
 *
 * WHY: Modify proposal before sending.
 * Note: Only DRAFT proposals can be updated.
 *
 * @param id - Proposal ID
 * @param data - Update data (partial)
 * @returns Updated proposal
 */
export async function updateProposal(id: number, data: ProposalUpdateRequest): Promise<Proposal> {
  return apiPut<Proposal>(`/api/proposals/${id}`, data);
}

/**
 * Delete proposal
 *
 * WHAT: Permanently removes a proposal.
 *
 * WHY: Cleanup of draft proposals no longer needed.
 * Note: Only DRAFT proposals can be deleted.
 *
 * @param id - Proposal ID
 */
export async function deleteProposal(id: number): Promise<void> {
  return apiDelete(`/api/proposals/${id}`);
}

/**
 * Get proposal statistics
 *
 * WHAT: Fetches aggregated proposal metrics.
 *
 * WHY: Dashboard widgets and pipeline overview.
 *
 * @returns Proposal statistics
 */
export async function getProposalStats(): Promise<ProposalStats> {
  return apiGet<ProposalStats>('/api/proposals/stats');
}

// =============================================================================
// Workflow Operations
// =============================================================================

/**
 * Send proposal to client
 *
 * WHAT: Transitions proposal from DRAFT to SENT.
 *
 * WHY: Makes proposal visible to client and starts approval workflow.
 * Records sent_at timestamp.
 *
 * @param id - Proposal ID
 * @returns Updated proposal
 */
export async function sendProposal(id: number): Promise<Proposal> {
  return apiPost<Proposal>(`/api/proposals/${id}/send`);
}

/**
 * Mark proposal as viewed
 *
 * WHAT: Transitions proposal from SENT to VIEWED.
 *
 * WHY: Tracks when client opens the proposal.
 * Can be called automatically or manually.
 *
 * @param id - Proposal ID
 * @returns Updated proposal
 */
export async function markProposalViewed(id: number): Promise<Proposal> {
  return apiPost<Proposal>(`/api/proposals/${id}/view`);
}

/**
 * Approve proposal
 *
 * WHAT: Transitions proposal to APPROVED status.
 *
 * WHY: Client accepts the proposal terms and pricing.
 * Updates project status to APPROVED.
 *
 * @param id - Proposal ID
 * @returns Updated proposal
 */
export async function approveProposal(id: number): Promise<Proposal> {
  return apiPost<Proposal>(`/api/proposals/${id}/approve`);
}

/**
 * Reject proposal
 *
 * WHAT: Transitions proposal to REJECTED status.
 *
 * WHY: Client declines the proposal with optional reason.
 * Reason helps improve future proposals.
 *
 * @param id - Proposal ID
 * @param data - Rejection data with optional reason
 * @returns Updated proposal
 */
export async function rejectProposal(id: number, data: ProposalRejectRequest = {}): Promise<Proposal> {
  return apiPost<Proposal>(`/api/proposals/${id}/reject`, data);
}

/**
 * Create proposal revision
 *
 * WHAT: Creates a new version of an existing proposal.
 *
 * WHY: Allows updating pricing/scope while preserving original.
 * Original is marked as REVISED, new version created as DRAFT.
 *
 * @param id - Original proposal ID
 * @param data - Changes for the revision
 * @returns New proposal version
 */
export async function reviseProposal(id: number, data: ProposalReviseRequest = {}): Promise<Proposal> {
  return apiPost<Proposal>(`/api/proposals/${id}/revise`, data);
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get pending proposals
 *
 * WHAT: Fetches proposals awaiting client response.
 *
 * WHY: Shortcut for filtering sent/viewed proposals.
 *
 * @param params - Optional pagination
 * @returns Pending proposals
 */
export async function getPendingProposals(
  params: Omit<ProposalListParams, 'pending_only'> = {}
): Promise<ProposalListResponse> {
  return getProposals({ ...params, pending_only: true });
}

/**
 * Get proposals for a project
 *
 * WHAT: Fetches all proposals for a specific project.
 *
 * WHY: Project detail view shows related proposals.
 *
 * @param projectId - Project ID
 * @param params - Optional pagination
 * @returns Proposals for project
 */
export async function getProposalsByProject(
  projectId: number,
  params: Omit<ProposalListParams, 'project_id'> = {}
): Promise<ProposalListResponse> {
  return getProposals({ ...params, project_id: projectId });
}
