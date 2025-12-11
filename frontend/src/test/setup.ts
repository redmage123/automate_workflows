/**
 * Test Setup
 *
 * WHAT: Global test configuration and DOM extensions.
 *
 * WHY: Provides consistent test environment with:
 * - DOM testing utilities from @testing-library/jest-dom
 * - Mock implementations for browser APIs
 * - Accessibility testing helpers
 *
 * HOW: Loaded before each test file by Vitest.
 */

import '@testing-library/jest-dom';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

/**
 * Cleanup after each test
 *
 * WHY: Prevents test pollution by unmounting React components
 * and clearing the DOM after each test.
 */
afterEach(() => {
  cleanup();
});

/**
 * Mock window.matchMedia
 *
 * WHY: JSDOM doesn't implement matchMedia, but our responsive
 * components may use it for media queries.
 */
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

/**
 * Mock localStorage
 *
 * WHY: Our auth store uses localStorage for token persistence.
 * This provides a working mock for tests.
 */
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

/**
 * Mock ResizeObserver
 *
 * WHY: Some UI components use ResizeObserver for responsive behavior.
 * JSDOM doesn't implement it.
 */
(globalThis as typeof globalThis & { ResizeObserver: typeof ResizeObserver }).ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
