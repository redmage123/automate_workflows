/**
 * Services Index
 *
 * WHAT: Central export point for all API service functions.
 *
 * WHY: Single import path for all API operations.
 *
 * HOW: Re-exports all named exports from individual service modules.
 */

export * from './api';
export * from './auth';
// Exclude getCurrentOrganization from organization as it's already exported from auth
export { updateOrganization, updateOrganizationSettings } from './organization';
export type { UpdateOrganizationRequest } from './organization';
export * from './projects';
export * from './proposals';
export * from './invoices';
export * from './workflows';
export * from './tickets';
