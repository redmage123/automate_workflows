/**
 * Test Utilities
 *
 * WHAT: Reusable test helpers and custom render functions.
 *
 * WHY: Provides consistent test setup with:
 * - Router context for components using react-router
 * - Query client for components using react-query
 * - Auth state mocking
 *
 * HOW: Wraps @testing-library/react render with providers.
 */

import type { ReactElement, ReactNode } from 'react';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/**
 * Create a fresh QueryClient for each test
 *
 * WHY: Prevents test pollution from cached queries.
 * Disables retries for faster test execution.
 */
function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

/**
 * Provider wrapper for tests
 *
 * WHY: Wraps components with all necessary context providers
 * for testing components that use routing, queries, etc.
 */
interface AllProvidersProps {
  children: ReactNode;
}

function AllProviders({ children }: AllProvidersProps): ReactElement {
  const queryClient = createTestQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
}

/**
 * Custom render function with providers
 *
 * WHAT: Renders component with all necessary providers.
 *
 * WHY: Most components need router and query context.
 * This provides them automatically.
 *
 * @param ui - Component to render
 * @param options - Additional render options
 * @returns Render result with all testing-library utilities
 *
 * @example
 * ```tsx
 * const { getByText } = renderWithProviders(<MyComponent />);
 * expect(getByText('Hello')).toBeInTheDocument();
 * ```
 */
export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
): RenderResult {
  return render(ui, { wrapper: AllProviders, ...options });
}

/**
 * Re-export everything from @testing-library/react
 *
 * WHY: Allows importing all testing utilities from one place.
 */
export * from '@testing-library/react';

/**
 * Override the default render with our custom version
 */
export { renderWithProviders as render };
