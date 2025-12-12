/**
 * Authentication Type Definitions
 *
 * WHAT: TypeScript types for authentication-related data structures.
 *
 * WHY: Strongly typed auth data ensures correct handling of user
 * credentials, tokens, and session state throughout the application.
 *
 * HOW: These types mirror the backend Pydantic schemas for auth endpoints.
 */

import type { BaseEntity, UserRole } from './common';

/**
 * User entity
 *
 * WHY: Represents the authenticated user with their role and org membership.
 */
export interface User extends BaseEntity {
  email: string;
  role: UserRole;
  org_id: number;
  is_active: boolean;
  email_verified: boolean;
}

/**
 * Organization entity
 *
 * WHY: Users belong to organizations for multi-tenant data isolation.
 */
export interface Organization extends BaseEntity {
  name: string;
  settings: OrganizationSettings;
  stripe_customer_id?: string;
}

/**
 * Organization settings
 *
 * WHY: Configurable organization preferences stored as JSON.
 */
export interface OrganizationSettings {
  timezone?: string;
  notification_email?: string;
  logo_url?: string;
}

/**
 * Login request payload
 *
 * WHY: Credentials sent to /auth/login endpoint.
 */
export interface LoginRequest {
  email: string;
  password: string;
}

/**
 * Registration request payload
 *
 * WHY: Data required to create new user and organization.
 */
export interface RegisterRequest {
  email: string;
  password: string;
  password_confirm: string;
  name: string;
  organization_name: string;
}

/**
 * Auth token response
 *
 * WHY: JWT tokens returned after successful authentication.
 */
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
}

/**
 * Registration response
 *
 * WHY: Confirmation data after successful registration.
 */
export interface RegisterResponse {
  message: string;
  user_id: number;
  org_id: number;
}

/**
 * Password reset request
 *
 * WHY: Initiate password reset flow by email.
 */
export interface PasswordResetRequest {
  email: string;
}

/**
 * Password reset confirmation
 *
 * WHY: Complete password reset with token and new password.
 */
export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}

/**
 * Token refresh request
 *
 * WHY: Get new access token using refresh token.
 */
export interface RefreshTokenRequest {
  refresh_token: string;
}

/**
 * Auth state for store
 *
 * WHY: Centralized auth state management with Zustand.
 */
export interface AuthState {
  user: User | null;
  organization: Organization | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

/**
 * Decoded JWT payload
 *
 * WHY: Structure of data encoded in JWT token.
 * Note: Never decode tokens client-side for auth decisions;
 * this is only for display purposes.
 */
export interface JwtPayload {
  user_id: number;
  org_id: number;
  role: UserRole;
  exp: number;
  iat: number;
}
