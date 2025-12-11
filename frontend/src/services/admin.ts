/**
 * Admin API Service
 *
 * WHAT: API functions for admin portal operations.
 *
 * WHY: Provides typed interface for admin endpoints including
 * user management, organization management, audit logs, and analytics.
 *
 * HOW: Uses authenticated API client with proper error handling.
 */

import { api } from './api';
import type {
  AdminUserListResponse,
  AdminUserDetail,
  AdminUserCreateRequest,
  AdminUserUpdateRequest,
  AdminUserListParams,
  AdminOrgListResponse,
  AdminOrgDetail,
  AdminOrgUpdateRequest,
  AdminOrgActionResponse,
  AdminOrgListParams,
  AuditLogListResponse,
  AuditLogListParams,
  ProjectMetricsResponse,
  RevenueMetricsResponse,
  UserActivityMetricsResponse,
  DashboardSummaryResponse,
} from '../types';

// ============================================================================
// User Management
// ============================================================================

/**
 * List all users (ADMIN only).
 */
export async function getAdminUsers(
  params?: AdminUserListParams
): Promise<AdminUserListResponse> {
  const response = await api.get<AdminUserListResponse>('/admin/users', {
    params,
  });
  return response.data;
}

/**
 * Get user details by ID (ADMIN only).
 */
export async function getAdminUser(userId: number): Promise<AdminUserDetail> {
  const response = await api.get<AdminUserDetail>(`/admin/users/${userId}`);
  return response.data;
}

/**
 * Create a new user (ADMIN only).
 */
export async function createAdminUser(
  data: AdminUserCreateRequest
): Promise<AdminUserDetail> {
  const response = await api.post<AdminUserDetail>('/admin/users', data);
  return response.data;
}

/**
 * Update user details (ADMIN only).
 */
export async function updateAdminUser(
  userId: number,
  data: AdminUserUpdateRequest
): Promise<AdminUserDetail> {
  const response = await api.put<AdminUserDetail>(
    `/admin/users/${userId}`,
    data
  );
  return response.data;
}

/**
 * Deactivate user (soft delete, ADMIN only).
 */
export async function deactivateAdminUser(userId: number): Promise<void> {
  await api.delete(`/admin/users/${userId}`);
}

/**
 * Force password reset for user (ADMIN only).
 */
export async function forcePasswordReset(
  userId: number
): Promise<{ message: string }> {
  const response = await api.post<{ message: string }>(
    `/admin/users/${userId}/reset-password`
  );
  return response.data;
}

// ============================================================================
// Organization Management
// ============================================================================

/**
 * List all organizations (ADMIN only).
 */
export async function getAdminOrganizations(
  params?: AdminOrgListParams
): Promise<AdminOrgListResponse> {
  const response = await api.get<AdminOrgListResponse>('/admin/organizations', {
    params,
  });
  return response.data;
}

/**
 * Get organization details by ID (ADMIN only).
 */
export async function getAdminOrganization(
  orgId: number
): Promise<AdminOrgDetail> {
  const response = await api.get<AdminOrgDetail>(`/admin/organizations/${orgId}`);
  return response.data;
}

/**
 * Update organization details (ADMIN only).
 */
export async function updateAdminOrganization(
  orgId: number,
  data: AdminOrgUpdateRequest
): Promise<AdminOrgDetail> {
  const response = await api.put<AdminOrgDetail>(
    `/admin/organizations/${orgId}`,
    data
  );
  return response.data;
}

/**
 * Suspend organization (ADMIN only).
 */
export async function suspendOrganization(
  orgId: number
): Promise<AdminOrgActionResponse> {
  const response = await api.post<AdminOrgActionResponse>(
    `/admin/organizations/${orgId}/suspend`
  );
  return response.data;
}

/**
 * Activate organization (ADMIN only).
 */
export async function activateOrganization(
  orgId: number
): Promise<AdminOrgActionResponse> {
  const response = await api.post<AdminOrgActionResponse>(
    `/admin/organizations/${orgId}/activate`
  );
  return response.data;
}

// ============================================================================
// Audit Logs
// ============================================================================

/**
 * List audit logs (ADMIN only).
 */
export async function getAuditLogs(
  params?: AuditLogListParams
): Promise<AuditLogListResponse> {
  const response = await api.get<AuditLogListResponse>('/admin/audit-logs', {
    params,
  });
  return response.data;
}

// ============================================================================
// Analytics
// ============================================================================

/**
 * Get project metrics (ADMIN only).
 */
export async function getProjectMetrics(
  months?: number
): Promise<ProjectMetricsResponse> {
  const response = await api.get<ProjectMetricsResponse>('/analytics/projects', {
    params: months ? { months } : undefined,
  });
  return response.data;
}

/**
 * Get revenue metrics (ADMIN only).
 */
export async function getRevenueMetrics(
  months?: number
): Promise<RevenueMetricsResponse> {
  const response = await api.get<RevenueMetricsResponse>('/analytics/revenue', {
    params: months ? { months } : undefined,
  });
  return response.data;
}

/**
 * Get user activity metrics (ADMIN only).
 */
export async function getUserActivityMetrics(
  months?: number
): Promise<UserActivityMetricsResponse> {
  const response = await api.get<UserActivityMetricsResponse>(
    '/analytics/users',
    {
      params: months ? { months } : undefined,
    }
  );
  return response.data;
}

/**
 * Get dashboard summary (ADMIN only).
 */
export async function getDashboardSummary(): Promise<DashboardSummaryResponse> {
  const response = await api.get<DashboardSummaryResponse>(
    '/analytics/dashboard'
  );
  return response.data;
}
