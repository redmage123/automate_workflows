/**
 * Authentication Service
 *
 * WHAT: API client methods for authentication endpoints.
 *
 * WHY: Encapsulates all auth-related API calls, providing a clean
 * interface for login, registration, logout, and token management.
 *
 * HOW: Uses the base API client with typed request/response handling.
 */

import { apiPost, apiGet, setTokens, clearTokens } from './api';
import type {
  AuthTokens,
  LoginRequest,
  RegisterRequest,
  RegisterResponse,
  PasswordResetRequest,
  PasswordResetConfirm,
  RefreshTokenRequest,
  User,
  Organization,
} from '../types';

/**
 * Login user
 *
 * WHAT: Authenticate user with email and password.
 *
 * WHY: Entry point for user authentication, returns JWT tokens
 * for subsequent authenticated requests.
 *
 * HOW: POST to /auth/login, store returned tokens.
 *
 * @param credentials - Email and password
 * @returns Auth tokens on success
 * @throws ApiError on failure
 */
export const login = async (credentials: LoginRequest): Promise<AuthTokens> => {
  const tokens = await apiPost<AuthTokens>('/api/auth/login', credentials);
  setTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
};

/**
 * Register new user and organization
 *
 * WHAT: Create new user account with associated organization.
 *
 * WHY: Self-service registration for new clients. Organization
 * is created automatically with user as first member.
 *
 * HOW: POST to /auth/register, returns confirmation.
 *
 * @param data - Registration data including org name
 * @returns Registration confirmation
 * @throws ApiError on failure (e.g., email exists)
 */
export const register = async (data: RegisterRequest): Promise<RegisterResponse> => {
  return apiPost<RegisterResponse>('/api/auth/register', data);
};

/**
 * Logout user
 *
 * WHAT: End user session.
 *
 * WHY: Invalidate tokens on server and clear local storage.
 * Prevents token reuse after logout.
 *
 * HOW: POST to /auth/logout, clear local tokens regardless of response.
 */
export const logout = async (): Promise<void> => {
  try {
    await apiPost('/api/auth/logout');
  } finally {
    // Always clear tokens, even if server request fails
    clearTokens();
  }
};

/**
 * Get current user
 *
 * WHAT: Fetch authenticated user's profile.
 *
 * WHY: Load user data on app init or after login.
 * Used to populate auth state with user details.
 *
 * HOW: GET to /auth/me with Bearer token.
 *
 * @returns Current user data
 * @throws ApiError if not authenticated
 */
export const getCurrentUser = async (): Promise<User> => {
  return apiGet<User>('/api/auth/me');
};

/**
 * Get current organization
 *
 * WHAT: Fetch user's organization details.
 *
 * WHY: Load org data for display and context.
 * Organization determines data scope for CLIENT users.
 *
 * HOW: GET to /orgs/me (user's org).
 *
 * @returns Current organization data
 * @throws ApiError if not authenticated
 */
export const getCurrentOrganization = async (): Promise<Organization> => {
  return apiGet<Organization>('/api/organizations/me');
};

/**
 * Request password reset
 *
 * WHAT: Initiate password reset flow.
 *
 * WHY: Self-service password recovery via email.
 * Sends reset link to user's email address.
 *
 * HOW: POST email to /auth/password-reset/request.
 *
 * @param data - Email address for reset
 */
export const requestPasswordReset = async (data: PasswordResetRequest): Promise<void> => {
  await apiPost('/api/auth/password-reset/request', data);
};

/**
 * Confirm password reset
 *
 * WHAT: Complete password reset with token.
 *
 * WHY: Final step of reset flow, sets new password.
 * Token from email link validates the request.
 *
 * HOW: POST token and new password to /auth/password-reset/confirm.
 *
 * @param data - Reset token and new password
 */
export const confirmPasswordReset = async (data: PasswordResetConfirm): Promise<void> => {
  await apiPost('/api/auth/password-reset/confirm', data);
};

/**
 * Refresh access token
 *
 * WHAT: Get new access token using refresh token.
 *
 * WHY: Access tokens expire after 24h; refresh tokens
 * allow getting new access tokens without re-login.
 *
 * HOW: POST refresh token to /auth/refresh.
 * Note: This is also handled automatically by the API interceptor.
 *
 * @param data - Refresh token
 * @returns New auth tokens
 */
export const refreshToken = async (data: RefreshTokenRequest): Promise<AuthTokens> => {
  const tokens = await apiPost<AuthTokens>('/api/auth/refresh', data);
  setTokens(tokens.access_token, tokens.refresh_token);
  return tokens;
};

/**
 * Verify email
 *
 * WHAT: Confirm user's email address.
 *
 * WHY: Email verification prevents fake accounts and
 * ensures we can contact the user.
 *
 * HOW: GET with verification token from email link.
 *
 * @param token - Verification token from email
 */
export const verifyEmail = async (token: string): Promise<void> => {
  await apiGet(`/api/auth/verify-email?token=${token}`);
};

/**
 * Resend verification email
 *
 * WHAT: Request new verification email.
 *
 * WHY: User may not have received or lost the original email.
 *
 * HOW: POST to /auth/resend-verification.
 */
export const resendVerificationEmail = async (): Promise<void> => {
  await apiPost('/api/auth/resend-verification');
};
