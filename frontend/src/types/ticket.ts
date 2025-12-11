/**
 * Ticket TypeScript Type Definitions
 *
 * WHAT: Type definitions for support ticketing features.
 *
 * WHY: Ensures type safety for ticket CRUD operations,
 * SLA tracking, comments, and UI components.
 *
 * HOW: Types match the backend Pydantic schemas for consistency.
 */

import type {
  OrgScopedEntity,
  TicketStatus,
  TicketPriority,
  TicketCategory,
} from './common';

/**
 * User reference for ticket displays
 *
 * WHAT: Minimal user info embedded in ticket responses.
 *
 * WHY: Avoids exposing full user details while providing
 * necessary info for display.
 */
export interface UserReference {
  id: number;
  email: string;
  name: string | null;
}

/**
 * SLA time remaining breakdown
 *
 * WHAT: Detailed countdown until SLA deadline.
 *
 * WHY: Enables countdown timers and progress bars in UI.
 */
export interface SLATimeRemaining {
  hours: number;
  minutes: number;
  seconds: number;
  total_seconds: number;
  is_breached: boolean;
  formatted: string;
}

/**
 * SLA status for a single timer
 *
 * WHAT: Current state of response or resolution SLA.
 *
 * WHY: Provides all info needed for SLA status display.
 */
export interface SLAStatus {
  due_at: string | null;
  is_met: boolean;
  is_breached: boolean;
  is_warning: boolean;
  time_remaining: SLATimeRemaining | null;
}

/**
 * Full SLA status response
 *
 * WHAT: Complete SLA information for a ticket.
 *
 * WHY: Single response with all SLA data for ticket details.
 */
export interface TicketSLAResponse {
  ticket_id: number;
  priority: TicketPriority;
  status: TicketStatus;
  sla_config: {
    response_hours: number;
    resolution_hours: number;
  };
  response: SLAStatus;
  resolution: SLAStatus;
}

/**
 * Ticket attachment
 *
 * WHAT: File attachment on a ticket or comment.
 *
 * WHY: Enables file sharing for screenshots, logs, etc.
 */
export interface TicketAttachment {
  id: number;
  ticket_id: number;
  comment_id: number | null;
  filename: string;
  file_size: number;
  mime_type: string;
  created_at: string;
  uploaded_by: UserReference | null;
  download_url: string | null;
}

/**
 * Ticket comment
 *
 * WHAT: Comment or internal note on a ticket.
 *
 * WHY: Enables conversation threading and private notes.
 */
export interface TicketComment {
  id: number;
  ticket_id: number;
  content: string;
  is_internal: boolean;
  is_edited: boolean;
  created_at: string;
  updated_at: string | null;
  user: UserReference | null;
  attachments: TicketAttachment[];
}

/**
 * Ticket entity (list view)
 *
 * WHAT: Ticket data for list views.
 *
 * WHY: Includes summary data without full comments.
 */
export interface Ticket extends OrgScopedEntity {
  project_id: number | null;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  category: TicketCategory;
  sla_response_due_at: string | null;
  sla_resolution_due_at: string | null;
  first_response_at: string | null;
  is_sla_response_breached: boolean;
  is_sla_resolution_breached: boolean;
  resolved_at: string | null;
  closed_at: string | null;
  created_by: UserReference | null;
  assigned_to: UserReference | null;
  comment_count: number;
  attachment_count: number;
}

/**
 * Ticket detail (full view)
 *
 * WHAT: Full ticket data with comments and attachments.
 *
 * WHY: Used for ticket detail view.
 */
export interface TicketDetail extends Ticket {
  comments: TicketComment[];
  attachments: TicketAttachment[];
  project_name: string | null;
}

/**
 * Ticket creation request
 *
 * WHAT: Data required to create a new ticket.
 *
 * WHY: Matches backend TicketCreate schema.
 */
export interface TicketCreateRequest {
  subject: string;
  description: string;
  project_id?: number | null;
  priority?: TicketPriority;
  category?: TicketCategory;
}

/**
 * Ticket update request
 *
 * WHAT: Data for updating an existing ticket.
 *
 * WHY: All fields optional for partial updates.
 */
export interface TicketUpdateRequest {
  subject?: string;
  description?: string;
  project_id?: number | null;
  priority?: TicketPriority;
  category?: TicketCategory;
}

/**
 * Ticket status change request
 *
 * WHAT: Data for changing ticket status.
 *
 * WHY: Status changes may have side effects (timestamps).
 */
export interface TicketStatusChangeRequest {
  status: TicketStatus;
  resolution_notes?: string;
}

/**
 * Ticket assignment request
 *
 * WHAT: Data for assigning a ticket.
 *
 * WHY: Assignment triggers notifications and status changes.
 */
export interface TicketAssignRequest {
  assigned_to_user_id: number | null;
}

/**
 * Comment creation request
 *
 * WHAT: Data for adding a comment.
 *
 * WHY: Matches backend CommentCreate schema.
 */
export interface CommentCreateRequest {
  content: string;
  is_internal?: boolean;
}

/**
 * Comment update request
 *
 * WHAT: Data for updating a comment.
 *
 * WHY: Only content can be updated.
 */
export interface CommentUpdateRequest {
  content: string;
}

/**
 * Ticket list response
 *
 * WHAT: Paginated list of tickets.
 *
 * WHY: Backend returns skip/limit pagination.
 */
export interface TicketListResponse {
  items: Ticket[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * Ticket statistics
 *
 * WHAT: Aggregated ticket metrics.
 *
 * WHY: Dashboard widgets and summary views.
 */
export interface TicketStats {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  open_count: number;
  sla_breached_count: number;
  avg_resolution_hours: number | null;
}

/**
 * Tickets at SLA risk
 *
 * WHAT: Breached and warning tickets.
 *
 * WHY: SLA monitoring dashboard.
 */
export interface SLAAtRiskResponse {
  breached: TicketSLASummary[];
  warning: TicketSLASummary[];
}

/**
 * Ticket SLA summary for at-risk lists
 *
 * WHAT: Compact ticket info for SLA dashboards.
 */
export interface TicketSLASummary {
  id: number;
  subject: string;
  priority: TicketPriority;
  status: TicketStatus;
  created_at: string;
  response_sla: {
    due_at: string | null;
    is_breached: boolean;
    time_remaining: SLATimeRemaining | null;
  };
  resolution_sla: {
    due_at: string | null;
    is_breached: boolean;
    time_remaining: SLATimeRemaining | null;
  };
}

/**
 * Ticket list query parameters
 *
 * WHAT: Filters and pagination for ticket list.
 *
 * WHY: Type-safe query building.
 */
export interface TicketListParams {
  skip?: number;
  limit?: number;
  status?: TicketStatus;
  priority?: TicketPriority;
  category?: TicketCategory;
  project_id?: number;
  assigned_to_me?: boolean;
  created_by_me?: boolean;
}

/**
 * Status display configuration
 *
 * WHAT: UI metadata for ticket statuses.
 *
 * WHY: Consistent status badges and colors.
 */
export const TICKET_STATUS_CONFIG: Record<
  TicketStatus,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  open: {
    label: 'Open',
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
    icon: 'inbox',
  },
  in_progress: {
    label: 'In Progress',
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-100',
    icon: 'clock',
  },
  waiting: {
    label: 'Waiting',
    color: 'text-purple-600',
    bgColor: 'bg-purple-100',
    icon: 'pause',
  },
  resolved: {
    label: 'Resolved',
    color: 'text-green-600',
    bgColor: 'bg-green-100',
    icon: 'check',
  },
  closed: {
    label: 'Closed',
    color: 'text-gray-600',
    bgColor: 'bg-gray-100',
    icon: 'archive',
  },
};

/**
 * Priority display configuration
 *
 * WHAT: UI metadata for ticket priorities.
 *
 * WHY: Consistent priority badges and SLA info.
 */
export const TICKET_PRIORITY_CONFIG: Record<
  TicketPriority,
  { label: string; color: string; bgColor: string; responseHours: number; resolutionHours: number }
> = {
  low: {
    label: 'Low',
    color: 'text-gray-600',
    bgColor: 'bg-gray-100',
    responseHours: 24,
    resolutionHours: 168,
  },
  medium: {
    label: 'Medium',
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
    responseHours: 8,
    resolutionHours: 72,
  },
  high: {
    label: 'High',
    color: 'text-orange-600',
    bgColor: 'bg-orange-100',
    responseHours: 4,
    resolutionHours: 24,
  },
  urgent: {
    label: 'Urgent',
    color: 'text-red-600',
    bgColor: 'bg-red-100',
    responseHours: 1,
    resolutionHours: 4,
  },
};

/**
 * Category display configuration
 *
 * WHAT: UI metadata for ticket categories.
 *
 * WHY: Consistent category badges and icons.
 */
export const TICKET_CATEGORY_CONFIG: Record<
  TicketCategory,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  general: {
    label: 'General',
    color: 'text-gray-600',
    bgColor: 'bg-gray-100',
    icon: 'document-text',
  },
  bug: {
    label: 'Bug',
    color: 'text-red-600',
    bgColor: 'bg-red-100',
    icon: 'bug',
  },
  feature: {
    label: 'Feature',
    color: 'text-purple-600',
    bgColor: 'bg-purple-100',
    icon: 'sparkles',
  },
  question: {
    label: 'Question',
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
    icon: 'question-mark-circle',
  },
  support: {
    label: 'Support',
    color: 'text-green-600',
    bgColor: 'bg-green-100',
    icon: 'lifebuoy',
  },
};

/**
 * Format user name from reference
 *
 * WHAT: Utility to display user name.
 *
 * WHY: Handles null values gracefully.
 */
export function formatUserName(user: UserReference | null): string {
  if (!user) return 'Unassigned';
  return user.name || user.email;
}

/**
 * Format file size for display
 *
 * WHAT: Human-readable file size.
 *
 * WHY: Better UX for attachment display.
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Format SLA time for display
 *
 * WHAT: Human-readable SLA countdown.
 *
 * WHY: Shows remaining time in appropriate units.
 */
export function formatSLATime(remaining: SLATimeRemaining | null): string {
  if (!remaining) return '-';
  if (remaining.is_breached) return 'BREACHED';
  return remaining.formatted;
}
