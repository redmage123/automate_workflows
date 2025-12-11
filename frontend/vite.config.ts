/**
 * Vite Configuration
 *
 * WHAT: Build tool configuration for development and production.
 *
 * WHY: Vite provides fast HMR in development and optimized builds
 * for production. This config adds testing support with Vitest.
 *
 * HOW: Extends default Vite config with React plugin and test configuration.
 */

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],

  /**
   * Test configuration
   *
   * WHY: Vitest provides Jest-compatible testing with native ESM support
   * and fast execution through Vite's transform pipeline.
   */
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/types/**',
      ],
    },
  },
});
