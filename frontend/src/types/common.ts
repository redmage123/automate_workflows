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
  DRAFT: 'draft',
  PROPOSAL_SENT: 'proposal_sent',
  APPROVED: 'approved',
  IN_PROGRESS: 'in_progress',
  ON_HOLD: 'on_hold',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
} as const;

export type ProjectStatus = (typeof ProjectStatus)[keyof typeof ProjectStatus];

/**
 * Project priority values
 *
 * WHY: Priority levels help with resource allocation and scheduling.
 */
export const ProjectPriority = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  URGENT: 'urgent',
} as const;

export type ProjectPriority = (typeof ProjectPriority)[keyof typeof ProjectPriority];

/**
 * Proposal status values
 *
 * WHY: Proposals have their own lifecycle separate from projects,
 * tracking the approval workflow.
 */
export const ProposalStatus = {
  DRAFT: 'draft',
  SENT: 'sent',
  VIEWED: 'viewed',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  EXPIRED: 'expired',
  REVISED: 'revised',
} as const;

export type ProposalStatus = (typeof ProposalStatus)[keyof typeof ProposalStatus];

/**
 * Invoice status values
 *
 * WHY: Tracks payment state for billing and reporting.
 * These match the backend InvoiceStatus enum.
 */
export const InvoiceStatus = {
  DRAFT: 'draft',
  SENT: 'sent',
  PAID: 'paid',
  PARTIALLY_PAID: 'partially_paid',
  OVERDUE: 'overdue',
  CANCELLED: 'cancelled',
  REFUNDED: 'refunded',
} as const;

export type InvoiceStatus = (typeof InvoiceStatus)[keyof typeof InvoiceStatus];

/**
 * Ticket status values
 *
 * WHY: Support tickets follow a standard helpdesk workflow.
 */
export const TicketStatus = {
  OPEN: 'open',
  IN_PROGRESS: 'in_progress',
  WAITING: 'waiting',
  RESOLVED: 'resolved',
  CLOSED: 'closed',
} as const;

export type TicketStatus = (typeof TicketStatus)[keyof typeof TicketStatus];

/**
 * Ticket priority values
 *
 * WHY: Priority determines SLA response/resolution times.
 */
export const TicketPriority = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  URGENT: 'urgent',
} as const;

export type TicketPriority = (typeof TicketPriority)[keyof typeof TicketPriority];

/**
 * Ticket category values
 *
 * WHY: Categories help with routing and reporting.
 */
export const TicketCategory = {
  GENERAL: 'general',
  BUG: 'bug',
  FEATURE: 'feature',
  QUESTION: 'question',
  SUPPORT: 'support',
} as const;

export type TicketCategory = (typeof TicketCategory)[keyof typeof TicketCategory];

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
