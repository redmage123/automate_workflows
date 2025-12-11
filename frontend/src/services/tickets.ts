/**
 * Ticket API Service
 *
 * WHAT: API client functions for ticket management operations.
 *
 * WHY: Encapsulates all ticket-related API calls with proper typing,
 * error handling, and query parameter building.
 *
 * HOW: Uses the base API client with typed request/response functions.
 */

import { apiGet, apiPost, apiPut, apiPatch, apiDelete } from './api';
import type {
  Ticket,
  TicketDetail,
  TicketCreateRequest,
  TicketUpdateRequest,
  TicketStatusChangeRequest,
  TicketAssignRequest,
  TicketListResponse,
  TicketStats,
  TicketListParams,
  TicketSLAResponse,
  SLAAtRiskResponse,
  TicketComment,
  CommentCreateRequest,
  CommentUpdateRequest,
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

// ============================================================================
// Ticket CRUD Operations
// ============================================================================

/**
 * Get paginated list of tickets
 *
 * WHAT: Fetches tickets with optional filters and pagination.
 *
 * WHY: Main method for ticket list views with filtering.
 *
 * @param params - Filter and pagination options
 * @returns Paginated ticket list
 */
export async function getTickets(params: TicketListParams = {}): Promise<TicketListResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiGet<TicketListResponse>(`/api/tickets${queryString}`);
}

/**
 * Get single ticket by ID with full details
 *
 * WHAT: Fetches ticket with comments and attachments.
 *
 * WHY: Used for ticket detail view.
 *
 * @param id - Ticket ID
 * @returns Ticket detail data
 */
export async function getTicket(id: number): Promise<TicketDetail> {
  return apiGet<TicketDetail>(`/api/tickets/${id}`);
}

/**
 * Create new ticket
 *
 * WHAT: Creates a ticket with SLA calculation.
 *
 * WHY: Users create tickets to report issues or request support.
 *
 * @param data - Ticket creation data
 * @returns Created ticket
 */
export async function createTicket(data: TicketCreateRequest): Promise<Ticket> {
  return apiPost<Ticket>('/api/tickets', data);
}

/**
 * Update ticket details
 *
 * WHAT: Updates ticket fields (not status).
 *
 * WHY: Modify ticket details like subject, description, priority.
 *
 * @param id - Ticket ID
 * @param data - Update data (partial)
 * @returns Updated ticket
 */
export async function updateTicket(id: number, data: TicketUpdateRequest): Promise<Ticket> {
  return apiPut<Ticket>(`/api/tickets/${id}`, data);
}

/**
 * Change ticket status
 *
 * WHAT: Changes ticket status with workflow validation.
 *
 * WHY: Status changes have business implications (SLA, timestamps).
 *
 * @param id - Ticket ID
 * @param data - New status
 * @returns Updated ticket
 */
export async function changeTicketStatus(
  id: number,
  data: TicketStatusChangeRequest
): Promise<Ticket> {
  return apiPatch<Ticket>(`/api/tickets/${id}/status`, data);
}

/**
 * Assign ticket to user
 *
 * WHAT: Assigns ticket and auto-transitions to IN_PROGRESS.
 *
 * WHY: Assignment indicates responsibility and starts work.
 *
 * @param id - Ticket ID
 * @param data - Assignment data (user ID or null to unassign)
 * @returns Updated ticket
 */
export async function assignTicket(id: number, data: TicketAssignRequest): Promise<Ticket> {
  return apiPatch<Ticket>(`/api/tickets/${id}/assign`, data);
}

/**
 * Delete ticket
 *
 * WHAT: Permanently removes a ticket.
 *
 * WHY: Cleanup of test data or spam tickets.
 * Note: Only ADMIN can delete.
 *
 * @param id - Ticket ID
 */
export async function deleteTicket(id: number): Promise<void> {
  return apiDelete(`/api/tickets/${id}`);
}

// ============================================================================
// Statistics and SLA
// ============================================================================

/**
 * Get ticket statistics
 *
 * WHAT: Fetches aggregated ticket metrics.
 *
 * WHY: Dashboard widgets and summary displays.
 *
 * @returns Ticket statistics
 */
export async function getTicketStats(): Promise<TicketStats> {
  return apiGet<TicketStats>('/api/tickets/stats');
}

/**
 * Get SLA status for a ticket
 *
 * WHAT: Fetches detailed SLA timing information.
 *
 * WHY: SLA countdown display and monitoring.
 *
 * @param id - Ticket ID
 * @returns SLA status
 */
export async function getTicketSLA(id: number): Promise<TicketSLAResponse> {
  return apiGet<TicketSLAResponse>(`/api/tickets/${id}/sla`);
}

/**
 * Get tickets at SLA risk
 *
 * WHAT: Fetches breached and warning tickets.
 *
 * WHY: SLA monitoring dashboard for proactive management.
 *
 * @returns Tickets at risk
 */
export async function getTicketsAtRisk(): Promise<SLAAtRiskResponse> {
  return apiGet<SLAAtRiskResponse>('/api/tickets/sla/at-risk');
}

// ============================================================================
// Comment Operations
// ============================================================================

/**
 * Add comment to ticket
 *
 * WHAT: Creates a comment or internal note.
 *
 * WHY: Enable communication and internal discussion.
 *
 * @param ticketId - Ticket ID
 * @param data - Comment data
 * @returns Created comment
 */
export async function addComment(ticketId: number, data: CommentCreateRequest): Promise<TicketComment> {
  return apiPost<TicketComment>(`/api/tickets/${ticketId}/comments`, data);
}

/**
 * Update comment
 *
 * WHAT: Updates comment content.
 *
 * WHY: Fix typos or add information.
 *
 * @param ticketId - Ticket ID
 * @param commentId - Comment ID
 * @param data - Update data
 * @returns Updated comment
 */
export async function updateComment(
  ticketId: number,
  commentId: number,
  data: CommentUpdateRequest
): Promise<TicketComment> {
  return apiPut<TicketComment>(`/api/tickets/${ticketId}/comments/${commentId}`, data);
}

/**
 * Delete comment
 *
 * WHAT: Removes a comment.
 *
 * WHY: Remove inappropriate or erroneous comments.
 *
 * @param ticketId - Ticket ID
 * @param commentId - Comment ID
 */
export async function deleteComment(ticketId: number, commentId: number): Promise<void> {
  return apiDelete(`/api/tickets/${ticketId}/comments/${commentId}`);
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get my tickets (created by me)
 *
 * WHAT: Convenience method to get user's own tickets.
 *
 * WHY: Common filter for "My Tickets" view.
 *
 * @param params - Additional filter options
 * @returns User's tickets
 */
export async function getMyTickets(
  params: Omit<TicketListParams, 'created_by_me'> = {}
): Promise<TicketListResponse> {
  return getTickets({ ...params, created_by_me: true });
}

/**
 * Get assigned tickets
 *
 * WHAT: Convenience method to get tickets assigned to current user.
 *
 * WHY: Common filter for "Assigned to Me" view.
 *
 * @param params - Additional filter options
 * @returns Assigned tickets
 */
export async function getAssignedTickets(
  params: Omit<TicketListParams, 'assigned_to_me'> = {}
): Promise<TicketListResponse> {
  return getTickets({ ...params, assigned_to_me: true });
}

/**
 * Get open tickets
 *
 * WHAT: Convenience method to get all non-closed tickets.
 *
 * WHY: Common filter for active ticket views.
 *
 * @param params - Additional filter options
 * @returns Open tickets
 */
export async function getOpenTickets(
  params: Omit<TicketListParams, 'status'> = {}
): Promise<TicketListResponse> {
  // Get tickets that are not closed
  // Note: API might need a specific "open" filter, for now we fetch all
  return getTickets(params);
}
