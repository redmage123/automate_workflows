/**
 * Project TypeScript Type Definitions
 *
 * WHAT: Type definitions for project management features.
 *
 * WHY: Ensures type safety for project CRUD operations,
 * API requests/responses, and UI components.
 *
 * HOW: Types match the backend Pydantic schemas for consistency.
 */

import type { OrgScopedEntity, ProjectStatus, ProjectPriority } from './common';

/**
 * Project entity
 *
 * WHAT: Full project data as returned by the API.
 *
 * WHY: Includes all fields for project display and management.
 */
export interface Project extends OrgScopedEntity {
  name: string;
  description: string | null;
  status: ProjectStatus;
  priority: ProjectPriority;
  estimated_hours: number | null;
  actual_hours: number | null;
  start_date: string | null;
  due_date: string | null;
  completed_at: string | null;
  is_active: boolean;
  is_overdue: boolean;
  hours_remaining: number | null;
}

/**
 * Project creation request
 *
 * WHAT: Data required to create a new project.
 *
 * WHY: Matches backend ProjectCreate schema.
 */
export interface ProjectCreateRequest {
  name: string;
  description?: string | null;
  priority?: ProjectPriority;
  estimated_hours?: number | null;
  start_date?: string | null;
  due_date?: string | null;
}

/**
 * Project update request
 *
 * WHAT: Data for updating an existing project.
 *
 * WHY: All fields optional for partial updates.
 */
export interface ProjectUpdateRequest {
  name?: string;
  description?: string | null;
  priority?: ProjectPriority;
  estimated_hours?: number | null;
  actual_hours?: number | null;
  start_date?: string | null;
  due_date?: string | null;
}

/**
 * Project status update request
 *
 * WHAT: Data for changing project status.
 *
 * WHY: Separate endpoint for status changes with audit logging.
 */
export interface ProjectStatusUpdateRequest {
  status: ProjectStatus;
}

/**
 * Project list response
 *
 * WHAT: Paginated list of projects.
 *
 * WHY: Backend returns skip/limit instead of page/pages.
 */
export interface ProjectListResponse {
  items: Project[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * Project statistics
 *
 * WHAT: Aggregated project metrics.
 *
 * WHY: Dashboard widgets and summary views.
 */
export interface ProjectStats {
  total: number;
  active: number;
  by_status: Record<string, number>;
  overdue: number;
}

/**
 * Project list query parameters
 *
 * WHAT: Filters and pagination for project list.
 *
 * WHY: Type-safe query building.
 */
export interface ProjectListParams {
  skip?: number;
  limit?: number;
  status?: ProjectStatus;
  priority?: ProjectPriority;
  active_only?: boolean;
  search?: string;
}

/**
 * Status display configuration
 *
 * WHAT: UI metadata for project statuses.
 *
 * WHY: Consistent status badges and colors.
 */
export const PROJECT_STATUS_CONFIG: Record<
  ProjectStatus,
  { label: string; color: string; bgColor: string }
> = {
  draft: { label: 'Draft', color: 'text-gray-600', bgColor: 'bg-gray-100' },
  proposal_sent: { label: 'Proposal Sent', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  approved: { label: 'Approved', color: 'text-green-600', bgColor: 'bg-green-100' },
  in_progress: { label: 'In Progress', color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  on_hold: { label: 'On Hold', color: 'text-orange-600', bgColor: 'bg-orange-100' },
  completed: { label: 'Completed', color: 'text-emerald-600', bgColor: 'bg-emerald-100' },
  cancelled: { label: 'Cancelled', color: 'text-red-600', bgColor: 'bg-red-100' },
};

/**
 * Priority display configuration
 *
 * WHAT: UI metadata for project priorities.
 *
 * WHY: Consistent priority badges and colors.
 */
export const PROJECT_PRIORITY_CONFIG: Record<
  ProjectPriority,
  { label: string; color: string; bgColor: string }
> = {
  low: { label: 'Low', color: 'text-gray-600', bgColor: 'bg-gray-100' },
  medium: { label: 'Medium', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  high: { label: 'High', color: 'text-orange-600', bgColor: 'bg-orange-100' },
  urgent: { label: 'Urgent', color: 'text-red-600', bgColor: 'bg-red-100' },
};
