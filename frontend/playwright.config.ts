/**
 * Playwright Configuration for Automation Platform E2E Tests
 *
 * WHAT: Configuration for running end-to-end tests with Playwright.
 *
 * WHY: Centralizes test configuration including:
 * - Browser selection and settings
 * - Viewport sizes for responsive testing
 * - Timeout configurations
 * - Reporter settings
 * - Base URL and environment variables
 *
 * HOW: Export a PlaywrightTestConfig object that Playwright uses
 * when running tests via `npx playwright test`.
 *
 * USAGE:
 *   npx playwright test                    # Run all tests
 *   npx playwright test --headed           # Run with visible browser
 *   npx playwright test --debug            # Debug mode with inspector
 *   npx playwright test e2e/app-workflows.spec.ts  # Run specific file
 *   npx playwright test --project=chromium # Run specific browser
 */

import { defineConfig, devices } from '@playwright/test';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// import dotenv from 'dotenv';
// dotenv.config({ path: '.env.test' });

export default defineConfig({
  /**
   * Test directory
   * WHY: Specifies where Playwright looks for test files.
   */
  testDir: './e2e',

  /**
   * Run tests in files in parallel
   * WHY: Set to false because authentication rate limits (5 req/min) would
   * cause failures when multiple test suites try to login simultaneously.
   * Serial execution ensures rate limits are not exceeded.
   */
  fullyParallel: false,

  /**
   * Fail the build on CI if you accidentally left test.only in the source code.
   * WHY: Prevents accidentally skipping tests in CI/CD pipelines.
   */
  forbidOnly: !!process.env.CI,

  /**
   * Retry on failure
   * WHY: Some tests are flaky due to rate limiting (5 req/min) and timing issues.
   * Retries help ensure stability, especially for authentication tests.
   * Mobile Chrome tests in particular often need retries after chromium exhausts rate limit.
   */
  retries: process.env.CI ? 3 : 2,

  /**
   * Limit workers to prevent rate limit issues
   * WHY: Multiple workers logging in simultaneously hit authentication rate limits.
   * Single worker ensures sequential test execution.
   */
  workers: 1,

  /**
   * Reporter to use
   * WHY: HTML reporter provides detailed test results with screenshots.
   */
  reporter: [
    ['html', { open: 'never' }],
    ['list'], // Console output
  ],

  /**
   * Shared settings for all the projects below.
   * See https://playwright.dev/docs/api/class-testoptions.
   */
  use: {
    /**
     * Base URL to use in actions like `await page.goto('/')`.
     * WHY: Allows using relative URLs in tests.
     */
    baseURL: process.env.BASE_URL || 'http://176.9.99.103:5101',

    /**
     * Collect trace when retrying the failed test.
     * WHY: Traces help debug test failures by recording all actions.
     * See https://playwright.dev/docs/trace-viewer
     */
    trace: 'on-first-retry',

    /**
     * Capture screenshot on failure
     * WHY: Visual evidence of test failures for debugging.
     */
    screenshot: 'only-on-failure',

    /**
     * Record video on failure
     * WHY: Videos help understand complex test failures.
     */
    video: 'on-first-retry',

    /**
     * Default navigation timeout
     * WHY: Prevents tests from hanging on slow network.
     */
    navigationTimeout: 30000,

    /**
     * Default action timeout
     * WHY: Prevents tests from waiting too long for elements.
     */
    actionTimeout: 10000,
  },

  /**
   * Global test timeout
   * WHY: Prevents individual tests from running indefinitely.
   */
  timeout: 60000,

  /**
   * Expect timeout
   * WHY: Default timeout for expect assertions.
   */
  expect: {
    timeout: 10000,
  },

  /**
   * Configure projects for major browsers
   * WHY: Tests should work across different browsers for compatibility.
   * NOTE: Firefox, WebKit, and Mobile Safari require additional browser installation.
   * Run `npx playwright install firefox webkit` to enable those browsers.
   * For now, only chromium-based browsers are enabled by default.
   */
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 800 },
      },
    },

    /* Mobile viewports - using chromium which is installed by default */
    {
      name: 'Mobile Chrome',
      use: {
        ...devices['Pixel 5'],
      },
    },

    /* Uncomment these after running: npx playwright install firefox webkit
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1280, height: 800 },
      },
    },

    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        viewport: { width: 1280, height: 800 },
      },
    },

    {
      name: 'Mobile Safari',
      use: {
        ...devices['iPhone 12'],
      },
    },

    {
      name: 'Tablet',
      use: {
        ...devices['iPad (gen 7)'],
      },
    },
    */
  ],

  /**
   * Run your local dev server before starting the tests.
   * WHY: Ensures the application is running before tests execute.
   *
   * NOTE: Commented out because we're testing against an already-running server.
   * Uncomment and modify if you want Playwright to start the dev server.
   */
  // webServer: {
  //   command: 'npm run dev',
  //   url: 'http://localhost:5173',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120 * 1000,
  // },

  /**
   * Output folder for test artifacts
   * WHY: Centralized location for screenshots, videos, traces.
   */
  outputDir: 'test-results/',

  /**
   * Global setup and teardown
   * WHY: Allows running setup/cleanup code before/after all tests.
   * Global setup clears Redis rate limit keys to prevent 429 errors during tests.
   */
  globalSetup: './e2e/global-setup.ts',
  // globalTeardown: require.resolve('./e2e/global-teardown'),
});
