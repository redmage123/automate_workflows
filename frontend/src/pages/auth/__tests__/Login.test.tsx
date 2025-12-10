/**
 * Login Page Tests
 *
 * WHAT: Unit and accessibility tests for the Login component.
 *
 * WHY: Ensures login functionality works correctly and meets
 * WCAG 2.1 Level AA accessibility standards.
 *
 * HOW: Uses Vitest with React Testing Library and jest-axe.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../../test/utils';
import { expectNoA11yViolations, getFocusableElements } from '../../../test/a11y';
import Login from '../Login';

// Default mock values
const mockLogin = vi.fn();
const mockSetError = vi.fn();
let mockIsLoading = false;
let mockError: string | null = null;

// Mock the auth store
vi.mock('../../../store', () => ({
  useAuthStore: () => ({
    login: mockLogin,
    isLoading: mockIsLoading,
    error: mockError,
    setError: mockSetError,
  }),
}));

describe('Login Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsLoading = false;
    mockError = null;
  });

  describe('Rendering', () => {
    it('should render login form with all required fields', () => {
      renderWithProviders(<Login />);

      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });

    it('should render links to registration and password reset', () => {
      renderWithProviders(<Login />);

      expect(screen.getByText(/create a new account/i)).toBeInTheDocument();
      expect(screen.getByText(/forgot your password/i)).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('should require email field', () => {
      renderWithProviders(<Login />);

      const emailInput = screen.getByLabelText(/email address/i);
      expect(emailInput).toHaveAttribute('required');
    });

    it('should require password field', () => {
      renderWithProviders(<Login />);

      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toHaveAttribute('required');
    });

    it('should have email type for email input', () => {
      renderWithProviders(<Login />);

      const emailInput = screen.getByLabelText(/email address/i);
      expect(emailInput).toHaveAttribute('type', 'email');
    });

    it('should have password type for password input', () => {
      renderWithProviders(<Login />);

      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toHaveAttribute('type', 'password');
    });
  });

  describe('Accessibility - WCAG 2.1 Level AA', () => {
    it('should have no accessibility violations', async () => {
      await expectNoA11yViolations(<Login />);
    });

    it('should have proper form labels', () => {
      renderWithProviders(<Login />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);

      // Inputs should be associated with labels
      expect(emailInput).toHaveAccessibleName();
      expect(passwordInput).toHaveAccessibleName();
    });

    it('should have focusable interactive elements', () => {
      const { container } = renderWithProviders(<Login />);

      const focusableElements = getFocusableElements(container);

      // Should include: email input, password input, forgot password link, sign in button, register link
      expect(focusableElements.length).toBeGreaterThanOrEqual(4);
    });

    it('should have proper heading hierarchy', () => {
      renderWithProviders(<Login />);

      const h1 = screen.getByRole('heading', { level: 1 });
      const h2 = screen.getByRole('heading', { level: 2 });

      expect(h1).toBeInTheDocument();
      expect(h2).toBeInTheDocument();
    });

    it('should have accessible submit button', () => {
      renderWithProviders(<Login />);

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      expect(submitButton).toHaveAccessibleName();
      expect(submitButton).not.toBeDisabled();
    });

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup();
      renderWithProviders(<Login />);

      const emailInput = screen.getByLabelText(/email address/i);

      // Focus the email input directly and verify keyboard navigation works
      emailInput.focus();
      expect(document.activeElement).toBe(emailInput);

      // Tab to next focusable element (password)
      await user.tab();
      const passwordInput = screen.getByLabelText(/password/i);
      expect(document.activeElement).toBe(passwordInput);
    });
  });

  describe('Form Submission', () => {
    it('should call login on form submit', async () => {
      const user = userEvent.setup();
      renderWithProviders(<Login />);

      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
      });
    });
  });
});
