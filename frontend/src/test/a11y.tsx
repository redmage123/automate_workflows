/**
 * Accessibility Testing Utilities
 *
 * WHAT: Helper functions for WCAG 2.1 Level AA compliance testing.
 *
 * WHY: Ensures all UI components meet accessibility standards:
 * - Screen reader compatibility
 * - Keyboard navigation
 * - Color contrast requirements
 * - Focus management
 *
 * HOW: Uses axe-core for automated accessibility auditing and
 * custom matchers for specific WCAG criteria.
 */

import type { ReactElement } from 'react';
import type { RenderResult } from '@testing-library/react';
import { configureAxe, toHaveNoViolations } from 'jest-axe';
import type { AxeResults } from 'axe-core';
import { renderWithProviders } from './utils';

// Extend expect with axe matchers
expect.extend(toHaveNoViolations);

/**
 * Configure axe-core for WCAG 2.1 Level AA
 *
 * WHY: We target Level AA as the baseline for accessibility,
 * which covers most critical accessibility requirements.
 */
const axe = configureAxe({
  rules: {
    // Ensure we check for Level AA compliance
    'color-contrast': { enabled: true },
    'link-name': { enabled: true },
    'button-name': { enabled: true },
    'image-alt': { enabled: true },
    'label': { enabled: true },
    'landmark-one-main': { enabled: true },
    'page-has-heading-one': { enabled: false }, // Disabled for component tests
    'region': { enabled: false }, // Disabled for component tests (needs full page context)
  },
});

/**
 * Render component and run accessibility audit
 *
 * WHAT: Combines React Testing Library render with axe audit.
 *
 * WHY: Provides convenient one-step accessibility testing.
 *
 * @param ui - React component to test
 * @returns Render result and axe results
 *
 * @example
 * ```tsx
 * const { results } = await renderWithA11y(<Button>Click me</Button>);
 * expect(results).toHaveNoViolations();
 * ```
 */
export async function renderWithA11y(
  ui: ReactElement
): Promise<{ renderResult: RenderResult; results: AxeResults }> {
  const renderResult = renderWithProviders(ui);
  // Cast to AxeResults to handle jest-axe/axe-core type version mismatch
  const results = (await axe(renderResult.container)) as unknown as AxeResults;
  return { renderResult, results };
}

/**
 * Run accessibility audit on existing container
 *
 * WHAT: Runs axe audit on an already-rendered container.
 *
 * WHY: Useful when component is already rendered or when
 * testing accessibility after interactions.
 *
 * @param container - DOM element to audit
 * @returns Axe results
 */
export async function checkA11y(container: Element): Promise<AxeResults> {
  // Cast to AxeResults to handle jest-axe/axe-core type version mismatch
  return (await axe(container)) as unknown as AxeResults;
}

/**
 * Format axe violations for readable test output
 *
 * WHAT: Creates human-readable violation messages.
 *
 * WHY: Default axe output can be verbose and hard to parse.
 * This provides actionable feedback for developers.
 *
 * @param results - Axe audit results
 * @returns Formatted violation string
 */
export function formatViolations(results: AxeResults): string {
  if (results.violations.length === 0) {
    return 'No accessibility violations found';
  }

  return results.violations
    .map((violation) => {
      const nodes = violation.nodes
        .map((node) => `  - ${node.html}\n    Fix: ${node.failureSummary}`)
        .join('\n');

      return `
${violation.id}: ${violation.description}
Impact: ${violation.impact}
Help: ${violation.helpUrl}
Elements:
${nodes}
`;
    })
    .join('\n---\n');
}

/**
 * Accessibility test helper with detailed error messages
 *
 * WHAT: Wrapper that provides better error output on failure.
 *
 * WHY: Makes it easier to identify and fix accessibility issues
 * during development.
 *
 * @param ui - React component to test
 *
 * @example
 * ```tsx
 * it('should be accessible', async () => {
 *   await expectNoA11yViolations(<MyComponent />);
 * });
 * ```
 */
export async function expectNoA11yViolations(ui: ReactElement): Promise<void> {
  const { results } = await renderWithA11y(ui);

  if (results.violations.length > 0) {
    throw new Error(
      `Accessibility violations found:\n${formatViolations(results)}`
    );
  }
}

/**
 * Check if element is focusable
 *
 * WHAT: Tests if an element can receive keyboard focus.
 *
 * WHY: Keyboard navigation is essential for accessibility.
 * All interactive elements must be focusable.
 *
 * @param element - DOM element to check
 * @returns true if element can receive focus
 */
export function isFocusable(element: Element): boolean {
  const focusableSelectors = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ];

  return focusableSelectors.some((selector) => element.matches(selector));
}

/**
 * Get all focusable elements within a container
 *
 * WHAT: Finds all keyboard-focusable elements.
 *
 * WHY: Useful for testing keyboard navigation order
 * and ensuring all interactive elements are reachable.
 *
 * @param container - Parent element to search within
 * @returns Array of focusable elements
 */
export function getFocusableElements(container: Element): Element[] {
  const focusableSelectors = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ].join(', ');

  return Array.from(container.querySelectorAll(focusableSelectors));
}
