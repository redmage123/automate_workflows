/**
 * Admin Types
 *
 * WHAT: TypeScript type definitions for admin portal.
 *
 * WHY: Type safety for admin operations including user management,
 * organization management, audit logs, and analytics.
 *
 * HOW: Mirrors backend Pydantic schemas for API consistency.
 */

// ============================================================================
// User Management Types
// ============================================================================

/**
 * User summary for list views.
 */
export interface AdminUserListItem {
  id: number;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  email_verified: boolean;
  org_id: number;
  org_name: string | null;
  created_at: string;
}

/**
 * Paginated user list response.
 */
export interface AdminUserListResponse {
  items: AdminUserListItem[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * Full user details for admin view.
 */
export interface AdminUserDetail {
  id: number;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  email_verified: boolean;
  org_id: number;
  org_name: string | null;
  created_at: string;
  updated_at: string | null;
}

/**
 * Admin-initiated user creation.
 */
export interface AdminUserCreateRequest {
  email: string;
  password: string;
  name?: string;
  org_id: number;
  role?: string;
}

/**
 * Admin user update request.
 */
export interface AdminUserUpdateRequest {
  name?: string;
  role?: string;
  is_active?: boolean;
}

/**
 * User list filter params.
 */
export interface AdminUserListParams {
  skip?: number;
  limit?: number;
  org_id?: number;
  role?: string;
  is_active?: boolean;
  search?: string;
}

// ============================================================================
// Organization Management Types
// ============================================================================

/**
 * Organization summary for list views.
 */
export interface AdminOrgListItem {
  id: number;
  name: string;
  is_active: boolean;
  user_count: number;
  project_count: number;
  created_at: string;
}

/**
 * Paginated organization list response.
 */
export interface AdminOrgListResponse {
  items: AdminOrgListItem[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * Full organization details for admin view.
 */
export interface AdminOrgDetail {
  id: number;
  name: string;
  is_active: boolean;
  user_count: number;
  project_count: number;
  total_revenue: number;
  created_at: string;
  updated_at: string | null;
}

/**
 * Admin organization update request.
 */
export interface AdminOrgUpdateRequest {
  name?: string;
}

/**
 * Suspend/activate response.
 */
export interface AdminOrgActionResponse {
  message: string;
  users_affected?: number;
}

/**
 * Organization list filter params.
 */
export interface AdminOrgListParams {
  skip?: number;
  limit?: number;
  is_active?: boolean;
  search?: string;
}

// ============================================================================
// Audit Log Types
// ============================================================================

/**
 * Audit log entry.
 */
export interface AuditLogItem {
  id: number;
  timestamp: string;
  action: string;
  resource_type: string;
  resource_id: number;
  actor_user_id: number;
  actor_user_email: string | null;
  org_id: number;
  org_name: string | null;
  ip_address: string | null;
  user_agent: string | null;
  extra_data: Record<string, unknown> | null;
}

/**
 * Paginated audit log response.
 */
export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * Audit log filter params.
 */
export interface AuditLogListParams {
  skip?: number;
  limit?: number;
  user_id?: number;
  org_id?: number;
  resource_type?: string;
  action?: string;
  start_date?: string;
  end_date?: string;
}

// ============================================================================
// Analytics Types
// ============================================================================

/**
 * Status count for breakdowns.
 */
export interface StatusCount {
  status: string;
  count: number;
}

/**
 * Organization metric.
 */
export interface OrganizationMetric {
  org_id: number;
  org_name: string;
  value: number;
}

/**
 * Time series point for charts.
 */
export interface TimeSeriesPoint {
  date: string;
  value: number;
}

/**
 * Project metrics response.
 */
export interface ProjectMetricsResponse {
  total_projects: number;
  by_status: StatusCount[];
  created_over_time: TimeSeriesPoint[];
  average_duration_days: number | null;
  projects_by_organization: OrganizationMetric[];
  active_projects: number;
  overdue_projects: number;
}

/**
 * Revenue metrics response.
 */
export interface RevenueMetricsResponse {
  total_revenue: number;
  revenue_mtd: number;
  revenue_ytd: number;
  revenue_by_organization: OrganizationMetric[];
  revenue_over_time: TimeSeriesPoint[];
  average_deal_size: number;
  payment_method_breakdown: StatusCount[];
  outstanding_amount: number;
  overdue_amount: number;
}

/**
 * User activity metrics response.
 */
export interface UserActivityMetricsResponse {
  total_users: number;
  active_users: number;
  recent_active_users: number;
  new_users_over_time: TimeSeriesPoint[];
  users_by_organization: OrganizationMetric[];
  users_by_role: StatusCount[];
  verified_users: number;
  unverified_users: number;
}

/**
 * Dashboard summary for quick overview.
 */
export interface DashboardSummaryResponse {
  total_users: number;
  total_organizations: number;
  active_organizations: number;
  total_projects: number;
  active_projects: number;
  total_revenue: number;
  revenue_mtd: number;
  open_tickets: number;
  overdue_tickets: number;
}
