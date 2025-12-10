/**
 * Base API Client
 *
 * WHAT: Axios-based HTTP client for backend API communication.
 *
 * WHY: Centralized API client provides:
 * - Consistent request/response handling
 * - Automatic token management
 * - Error handling and transformation
 * - Request/response interceptors
 *
 * HOW: Axios instance configured with base URL, interceptors for auth,
 * and error transformation to match our ApiError type.
 */

import axios, {
  type AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import type { ApiError } from '../types';

/**
 * API base URL from environment
 *
 * WHY: Environment-based configuration allows different URLs
 * for development, staging, and production.
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Token storage keys
 *
 * WHY: Consistent keys for localStorage access.
 */
const TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

/**
 * Get stored access token
 *
 * WHAT: Retrieves access token from localStorage.
 *
 * WHY: Tokens are stored in localStorage for persistence
 * across page refreshes. Note: Consider httpOnly cookies
 * for production security.
 */
export const getAccessToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

/**
 * Get stored refresh token
 */
export const getRefreshToken = (): string | null => {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

/**
 * Store auth tokens
 *
 * WHAT: Saves tokens to localStorage.
 *
 * WHY: Persist tokens for session continuity.
 */
export const setTokens = (accessToken: string, refreshToken: string): void => {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
};

/**
 * Clear auth tokens
 *
 * WHAT: Remove tokens from localStorage.
 *
 * WHY: Called on logout or auth failure.
 */
export const clearTokens = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

/**
 * Check if user is authenticated
 *
 * WHAT: Verify presence of access token.
 *
 * WHY: Quick check for auth state without decoding token.
 * Note: Token might be expired; backend validates.
 */
export const isAuthenticated = (): boolean => {
  return !!getAccessToken();
};

/**
 * Create configured Axios instance
 *
 * WHAT: Factory function for API client.
 *
 * WHY: Allows multiple instances with different configs if needed.
 *
 * HOW: Configures base URL, headers, interceptors.
 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: 30000, // 30 second timeout
  });

  /**
   * Request interceptor
   *
   * WHAT: Adds auth token to outgoing requests.
   *
   * WHY: Automatically include Bearer token for authenticated requests.
   */
  client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const token = getAccessToken();
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error: AxiosError) => {
      return Promise.reject(error);
    }
  );

  /**
   * Response interceptor
   *
   * WHAT: Transform responses and handle errors.
   *
   * WHY: Consistent error handling and potential token refresh.
   *
   * HOW: On 401, attempt token refresh; on other errors, transform
   * to ApiError format.
   */
  client.interceptors.response.use(
    (response: AxiosResponse) => {
      return response;
    },
    async (error: AxiosError<ApiError>) => {
      const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

      // Handle 401 Unauthorized - attempt token refresh
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        const refreshToken = getRefreshToken();
        if (refreshToken) {
          try {
            const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
              refresh_token: refreshToken,
            });

            const { access_token } = response.data;
            localStorage.setItem(TOKEN_KEY, access_token);

            // Retry original request with new token
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${access_token}`;
            }
            return client(originalRequest);
          } catch {
            // Refresh failed, clear tokens and redirect to login
            clearTokens();
            window.location.href = '/login';
            return Promise.reject(error);
          }
        } else {
          // No refresh token, redirect to login
          clearTokens();
          window.location.href = '/login';
        }
      }

      // Transform error to ApiError format
      const apiError: ApiError = error.response?.data || {
        error: 'NetworkError',
        message: error.message || 'Network request failed',
        status_code: error.response?.status || 0,
      };

      return Promise.reject(apiError);
    }
  );

  return client;
};

/**
 * Default API client instance
 *
 * WHAT: Singleton axios instance for API calls.
 *
 * WHY: Single instance ensures consistent configuration
 * and interceptor behavior across the application.
 */
export const api = createApiClient();

/**
 * HTTP method helpers
 *
 * WHAT: Typed wrapper functions for common HTTP methods.
 *
 * WHY: Provides better TypeScript inference and cleaner syntax.
 */

export const apiGet = <T>(url: string, config?: AxiosRequestConfig): Promise<T> =>
  api.get<T>(url, config).then((res) => res.data);

export const apiPost = <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> =>
  api.post<T>(url, data, config).then((res) => res.data);

export const apiPut = <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> =>
  api.put<T>(url, data, config).then((res) => res.data);

export const apiPatch = <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> =>
  api.patch<T>(url, data, config).then((res) => res.data);

export const apiDelete = <T>(url: string, config?: AxiosRequestConfig): Promise<T> =>
  api.delete<T>(url, config).then((res) => res.data);

export default api;
