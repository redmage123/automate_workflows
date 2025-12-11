/**
 * Project API Service
 *
 * WHAT: API client functions for project management operations.
 *
 * WHY: Encapsulates all project-related API calls with proper typing,
 * error handling, and query parameter building.
 *
 * HOW: Uses the base API client with typed request/response functions.
 */

import { apiGet, apiPost, apiPut, apiPatch, apiDelete } from './api';
import type {
  Project,
  ProjectCreateRequest,
  ProjectUpdateRequest,
  ProjectStatusUpdateRequest,
  ProjectListResponse,
  ProjectStats,
  ProjectListParams,
} from '../types';
import type { ProposalListResponse } from '../types';

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
 * Get paginated list of projects
 *
 * WHAT: Fetches projects with optional filters and pagination.
 *
 * WHY: Main method for project list views with filtering.
 *
 * @param params - Filter and pagination options
 * @returns Paginated project list
 */
export async function getProjects(params: ProjectListParams = {}): Promise<ProjectListResponse> {
  const queryString = buildQueryString(params as Record<string, unknown>);
  return apiGet<ProjectListResponse>(`/api/projects${queryString}`);
}

/**
 * Get single project by ID
 *
 * WHAT: Fetches full project details.
 *
 * WHY: Used for project detail views and editing.
 *
 * @param id - Project ID
 * @returns Project data
 */
export async function getProject(id: number): Promise<Project> {
  return apiGet<Project>(`/api/projects/${id}`);
}

/**
 * Create new project
 *
 * WHAT: Creates a project in DRAFT status.
 *
 * WHY: ADMINs create projects to track client work.
 *
 * @param data - Project creation data
 * @returns Created project
 */
export async function createProject(data: ProjectCreateRequest): Promise<Project> {
  return apiPost<Project>('/api/projects', data);
}

/**
 * Update project details
 *
 * WHAT: Updates project fields (not status).
 *
 * WHY: Modify project details like name, description, dates.
 *
 * @param id - Project ID
 * @param data - Update data (partial)
 * @returns Updated project
 */
export async function updateProject(id: number, data: ProjectUpdateRequest): Promise<Project> {
  return apiPut<Project>(`/api/projects/${id}`, data);
}

/**
 * Update project status
 *
 * WHAT: Changes project status with validation.
 *
 * WHY: Status changes have business implications and are audited.
 *
 * @param id - Project ID
 * @param data - New status
 * @returns Updated project
 */
export async function updateProjectStatus(
  id: number,
  data: ProjectStatusUpdateRequest
): Promise<Project> {
  return apiPatch<Project>(`/api/projects/${id}/status`, data);
}

/**
 * Delete project
 *
 * WHAT: Permanently removes a project.
 *
 * WHY: Cleanup of test data or cancelled projects.
 * Note: Only ADMIN can delete.
 *
 * @param id - Project ID
 */
export async function deleteProject(id: number): Promise<void> {
  return apiDelete(`/api/projects/${id}`);
}

/**
 * Get project statistics
 *
 * WHAT: Fetches aggregated project metrics.
 *
 * WHY: Dashboard widgets and summary displays.
 *
 * @returns Project statistics
 */
export async function getProjectStats(): Promise<ProjectStats> {
  return apiGet<ProjectStats>('/api/projects/stats');
}

/**
 * Search projects by name
 *
 * WHAT: Full-text search across project names.
 *
 * WHY: Quick project lookup for users.
 *
 * @param query - Search query (min 3 chars)
 * @param params - Optional pagination
 * @returns Matching projects
 */
export async function searchProjects(
  query: string,
  params: Omit<ProjectListParams, 'search'> = {}
): Promise<ProjectListResponse> {
  return getProjects({ ...params, search: query });
}

/**
 * Get proposals for a project
 *
 * WHAT: Fetches all proposals associated with a project.
 *
 * WHY: Project detail view shows related proposals.
 *
 * @param projectId - Project ID
 * @returns List of proposals
 */
export async function getProjectProposals(projectId: number): Promise<ProposalListResponse> {
  return apiGet<ProposalListResponse>(`/api/projects/${projectId}/proposals`);
}
