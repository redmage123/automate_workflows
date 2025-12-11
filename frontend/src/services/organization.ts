/**
 * Organization Service
 *
 * WHAT: API calls for organization management.
 *
 * WHY: Centralized organization operations provide:
 * - Type-safe API calls for org CRUD
 * - Reusable across components
 * - Consistent error handling
 *
 * HOW: Uses the base API client for HTTP requests.
 */

import { apiPut, apiPatch } from './api';
import type { Organization, OrganizationSettings } from '../types';

// Re-export getCurrentOrganization from auth to maintain backwards compatibility
export { getCurrentOrganization } from './auth';

/**
 * Organization update request
 */
export interface UpdateOrganizationRequest {
  name?: string;
  settings?: OrganizationSettings;
}

/**
 * Update organization
 *
 * WHAT: Update organization name and/or settings.
 *
 * WHY: Allow organization admins to modify org details.
 *
 * @param data - Fields to update
 */
export const updateOrganization = async (
  data: UpdateOrganizationRequest
): Promise<Organization> => {
  return apiPatch<Organization>('/api/organizations/me', data);
};

/**
 * Update organization settings
 *
 * WHAT: Update only organization settings.
 *
 * WHY: Convenience method for settings-only updates.
 *
 * @param settings - New settings values
 */
export const updateOrganizationSettings = async (
  settings: OrganizationSettings
): Promise<Organization> => {
  return apiPut<Organization>('/api/organizations/me/settings', { settings });
};
