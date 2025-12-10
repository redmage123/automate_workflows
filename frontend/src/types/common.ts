/**
 * Common TypeScript Type Definitions
 *
 * WHAT: Shared type definitions used across the application.
 *
 * WHY: Centralized type definitions ensure type safety and consistency
 * across components, reducing bugs and improving developer experience
 * with IDE autocompletion.
 *
 * HOW: These types are imported wherever needed and serve as the single
 * source of truth for data structures.
 */

/**
 * User role values
 *
 * WHY: Two distinct roles with different permissions:
 * - ADMIN: Service provider with full access
 * - CLIENT: Customer with org-scoped access
 */
export const UserRole = {
  ADMIN: 'ADMIN',
  CLIENT: 'CLIENT',
} as const;

export type UserRole = (typeof UserRole)[keyof typeof UserRole];

/**
 * Project status values
 *
 * WHY: Projects follow a defined lifecycle from creation to completion.
 * Status transitions are validated on the backend.
 */
export const ProjectStatus = {
  DRAFT: 'DRAFT',
  PROPOSED: 'PROPOSED',
  APPROVED: 'APPROVED',
  IN_PROGRESS: 'IN_PROGRESS',
  COMPLETED: 'COMPLETED',
  ARCHIVED: 'ARCHIVED',
} as const;

export type ProjectStatus = (typeof ProjectStatus)[keyof typeof ProjectStatus];

/**
 * Proposal status values
 *
 * WHY: Proposals have their own lifecycle separate from projects,
 * tracking the approval workflow.
 */
export const ProposalStatus = {
  DRAFT: 'DRAFT',
  SENT: 'SENT',
  VIEWED: 'VIEWED',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
  EXPIRED: 'EXPIRED',
} as const;

export type ProposalStatus = (typeof ProposalStatus)[keyof typeof ProposalStatus];

/**
 * Invoice status values
 *
 * WHY: Tracks payment state for billing and reporting.
 */
export const InvoiceStatus = {
  PENDING: 'PENDING',
  PAID: 'PAID',
  FAILED: 'FAILED',
  REFUNDED: 'REFUNDED',
} as const;

export type InvoiceStatus = (typeof InvoiceStatus)[keyof typeof InvoiceStatus];

/**
 * Ticket status values
 *
 * WHY: Support tickets follow a standard helpdesk workflow.
 */
export const TicketStatus = {
  OPEN: 'OPEN',
  IN_PROGRESS: 'IN_PROGRESS',
  WAITING: 'WAITING',
  RESOLVED: 'RESOLVED',
  CLOSED: 'CLOSED',
} as const;

export type TicketStatus = (typeof TicketStatus)[keyof typeof TicketStatus];

/**
 * Ticket priority values
 *
 * WHY: Priority determines SLA response/resolution times.
 */
export const TicketPriority = {
  LOW: 'LOW',
  MEDIUM: 'MEDIUM',
  HIGH: 'HIGH',
  URGENT: 'URGENT',
} as const;

export type TicketPriority = (typeof TicketPriority)[keyof typeof TicketPriority];

/**
 * Workflow status values
 *
 * WHY: Tracks n8n workflow instance state.
 */
export const WorkflowStatus = {
  ACTIVE: 'ACTIVE',
  PAUSED: 'PAUSED',
  ERROR: 'ERROR',
  DELETED: 'DELETED',
} as const;

export type WorkflowStatus = (typeof WorkflowStatus)[keyof typeof WorkflowStatus];

/**
 * Pagination parameters
 *
 * WHY: Consistent pagination across all list endpoints.
 */
export interface PaginationParams {
  page?: number;
  limit?: number;
}

/**
 * Paginated response wrapper
 *
 * WHY: All list endpoints return paginated data with metadata
 * for building pagination UI components.
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
  limit: number;
}

/**
 * API error response
 *
 * WHY: Consistent error structure from backend allows uniform
 * error handling in the frontend.
 */
export interface ApiError {
  error: string;
  message: string;
  status_code: number;
  details?: Record<string, unknown>;
}

/**
 * Base entity with common fields
 *
 * WHY: All entities have id and timestamps, reducing duplication.
 */
export interface BaseEntity {
  id: number;
  created_at: string;
  updated_at: string;
}

/**
 * Multi-tenant entity with organization scope
 *
 * WHY: Most entities belong to an organization for data isolation.
 */
export interface OrgScopedEntity extends BaseEntity {
  org_id: number;
}

/**
 * Sort direction for list queries
 */
export type SortDirection = 'asc' | 'desc';

/**
 * Generic sort parameters
 */
export interface SortParams {
  field: string;
  direction: SortDirection;
}

/**
 * Filter operator types for advanced queries
 */
export type FilterOperator = 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'in';

/**
 * Generic filter parameter
 */
export interface FilterParam {
  field: string;
  operator: FilterOperator;
  value: unknown;
}
