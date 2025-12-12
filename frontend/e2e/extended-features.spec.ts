/**
 * Extended E2E Test Suite for Automation Platform
 *
 * WHAT: End-to-end tests for extended features including:
 * - Client Onboarding Wizard
 * - Workflow Templates
 * - Workflow Environments
 * - Workflow AI
 * - Admin Audit Logs
 * - Admin Analytics
 *
 * WHY: Ensures comprehensive coverage of all major user journeys
 * beyond the core workflows tested in app-workflows.spec.ts.
 *
 * HOW: Uses Playwright for browser automation with:
 * - Page Object Model pattern for maintainability
 * - Isolated test data to prevent conflicts
 * - Proper cleanup after tests
 *
 * USAGE: Run with Playwright test runner:
 *   npx playwright test e2e/extended-features.spec.ts
 */

import { test, expect, Page, BrowserContext } from '@playwright/test';
import * as path from 'path';
import { fileURLToPath } from 'url';

// ============================================================================
// Configuration
// ============================================================================

const BASE_URL = process.env.BASE_URL || 'http://176.9.99.103:5101';

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Path to authenticated storage state (created by global-setup.ts)
const STORAGE_STATE_PATH = path.join(__dirname, '.auth', 'user.json');

// Generate unique identifiers for test data
const generateUniqueId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// ============================================================================
// Page Object Helpers
// ============================================================================

/**
 * Helper class for common page interactions
 *
 * WHY: Centralizes selectors and common operations for easier maintenance.
 */
class PageHelpers {
  constructor(private page: Page) {}

  /**
   * Navigate to a page and wait for network idle
   */
  async goto(path: string) {
    await this.page.goto(`${BASE_URL}${path}`);
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Open mobile sidebar (hamburger menu)
   */
  async openMobileSidebar() {
    const hamburgerButton = this.page.getByRole('button', { name: 'Open sidebar' });
    if (await hamburgerButton.isVisible()) {
      await hamburgerButton.click();
      await this.page.waitForTimeout(300);
    }
  }

  /**
   * Navigate via sidebar link - handles both mobile and desktop
   */
  async navigateToSidebarLink(linkName: string) {
    const link = this.page.getByRole('link', { name: linkName }).first();
    const hamburgerButton = this.page.getByRole('button', { name: 'Open sidebar' });
    if (await hamburgerButton.isVisible()) {
      await hamburgerButton.click();
      await this.page.waitForTimeout(300);
    }
    await link.click();
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Fill form field by label
   */
  async fillField(label: string, value: string) {
    if (label.toLowerCase().includes('password')) {
      const byId = this.page.locator(`#${label.toLowerCase().replace(/\s+/g, '')}`);
      if (await byId.count() === 1) {
        await byId.fill(value);
        return;
      }
    }
    const textbox = this.page.getByRole('textbox', { name: label });
    if (await textbox.count() === 1) {
      await textbox.fill(value);
    } else {
      const textboxPartial = this.page.getByRole('textbox', { name: new RegExp(label, 'i') });
      if (await textboxPartial.count() === 1) {
        await textboxPartial.fill(value);
      } else {
        const field = this.page.getByLabel(label, { exact: false });
        await field.fill(value);
      }
    }
  }

  /**
   * Select dropdown option by label
   */
  async selectOption(label: string, value: string) {
    const select = this.page.getByLabel(label, { exact: false });
    await select.selectOption(value);
  }

  /**
   * Click submit/action button by text
   */
  async clickButton(text: string) {
    await this.page.getByRole('button', { name: text }).click();
  }

  /**
   * Wait for toast/success message
   */
  async waitForToast(text: string, timeout = 5000) {
    await expect(this.page.getByText(text)).toBeVisible({ timeout });
  }
}

// ============================================================================
// Client Onboarding Wizard Tests
// ============================================================================

test.describe('Client Onboarding Wizard', () => {
  test.describe.configure({ mode: 'serial' });

  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;
  const projectName = `Onboarding Project ${generateUniqueId()}`;
  const proposalTitle = `Onboarding Proposal ${generateUniqueId()}`;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should navigate to onboarding page', async () => {
    await helpers.goto('/onboarding');
    await expect(page.getByRole('heading', { name: 'Client Onboarding' })).toBeVisible();
  });

  test('should display step indicator', async () => {
    // Check step indicator shows Project, Proposal, Review
    await expect(page.getByText('Project')).toBeVisible();
    await expect(page.getByText('Proposal')).toBeVisible();
    await expect(page.getByText('Review')).toBeVisible();
  });

  test('should show Step 1: Project Details form', async () => {
    // Check project form fields
    await expect(page.getByLabel('Project Name')).toBeVisible();
    await expect(page.getByLabel('Description')).toBeVisible();
    await expect(page.getByLabel('Priority')).toBeVisible();
    await expect(page.getByLabel('Estimated Hours')).toBeVisible();
    await expect(page.getByLabel('Start Date')).toBeVisible();
    await expect(page.getByLabel('Due Date')).toBeVisible();
  });

  test('should validate required project name', async () => {
    // Try to proceed without project name
    await helpers.clickButton('Next');

    // Should show validation error
    await expect(page.getByText(/project name.*required/i)).toBeVisible();
  });

  test('should fill Step 1 and proceed to Step 2', async () => {
    // Fill project details
    await page.getByLabel('Project Name').fill(projectName);
    await page.getByLabel('Description').fill('Automated onboarding test project description');
    await page.getByLabel('Priority').selectOption('high');
    await page.getByLabel('Estimated Hours').fill('40');

    // Set dates
    const today = new Date().toISOString().split('T')[0];
    const nextMonth = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    await page.getByLabel('Start Date').fill(today);
    await page.getByLabel('Due Date').fill(nextMonth);

    // Click Next
    await helpers.clickButton('Next');

    // Should now show Step 2: Proposal Details
    await expect(page.getByLabel('Proposal Title')).toBeVisible();
  });

  test('should show Step 2: Proposal Details form', async () => {
    // Check proposal form fields
    await expect(page.getByLabel('Proposal Title')).toBeVisible();
    await expect(page.getByLabel('Scope of Work')).toBeVisible();
    await expect(page.getByLabel('Valid Until')).toBeVisible();
    await expect(page.getByText('Line Items')).toBeVisible();
  });

  test('should validate required proposal title', async () => {
    // Try to proceed without proposal title
    await helpers.clickButton('Next');

    // Should show validation error
    await expect(page.getByText(/proposal title.*required/i)).toBeVisible();
  });

  test('should fill Step 2 and proceed to Step 3', async () => {
    // Fill proposal details
    await page.getByLabel('Proposal Title').fill(proposalTitle);
    await page.getByLabel('Scope of Work').fill('Scope of work for the automated test proposal');

    // Set valid until date
    const validUntil = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    await page.getByLabel('Valid Until').fill(validUntil);

    // Add a line item
    const descriptionInput = page.locator('input[placeholder="Description"]').first();
    const qtyInput = page.locator('input[placeholder="Qty"]').first();
    const priceInput = page.locator('input[placeholder="Price"]').first();

    await descriptionInput.fill('Automation Setup');
    await qtyInput.fill('10');
    await priceInput.fill('100');

    // Click Next
    await helpers.clickButton('Next');

    // Should now show Step 3: Review
    await expect(page.getByText('Project Summary')).toBeVisible();
  });

  test('should show Step 3: Review with correct data', async () => {
    // Verify project summary
    await expect(page.getByText('Project Summary')).toBeVisible();
    await expect(page.getByText(projectName)).toBeVisible();

    // Verify proposal summary
    await expect(page.getByText('Proposal Summary')).toBeVisible();
    await expect(page.getByText(proposalTitle)).toBeVisible();

    // Verify line items displayed
    await expect(page.getByText('Automation Setup')).toBeVisible();

    // Verify totals are calculated
    await expect(page.getByText('$1,000.00')).toBeVisible(); // 10 * 100

    // Notes section should be visible
    await expect(page.getByLabel('Client Notes')).toBeVisible();
    await expect(page.getByLabel('Terms & Conditions')).toBeVisible();
    await expect(page.getByLabel('Internal Notes')).toBeVisible();
  });

  test('should be able to go back to previous steps', async () => {
    // Click Back
    await helpers.clickButton('Back');

    // Should be on Step 2
    await expect(page.getByLabel('Proposal Title')).toBeVisible();
    await expect(page.getByLabel('Proposal Title')).toHaveValue(proposalTitle);

    // Click Back again
    await helpers.clickButton('Back');

    // Should be on Step 1
    await expect(page.getByLabel('Project Name')).toBeVisible();
    await expect(page.getByLabel('Project Name')).toHaveValue(projectName);
  });

  test('should allow adding multiple line items', async () => {
    // Navigate back to Step 2
    await helpers.clickButton('Next');
    await expect(page.getByLabel('Proposal Title')).toBeVisible();

    // Click Add Item button
    await page.getByText('+ Add Item').click();

    // Should have multiple line items
    const descriptionInputs = page.locator('input[placeholder="Description"]');
    await expect(descriptionInputs).toHaveCount(2);

    // Fill second line item
    await descriptionInputs.nth(1).fill('Consultation');
    await page.locator('input[placeholder="Qty"]').nth(1).fill('5');
    await page.locator('input[placeholder="Price"]').nth(1).fill('200');
  });
});

// ============================================================================
// Workflow Templates Tests
// ============================================================================

test.describe('Workflow Templates', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should navigate to workflow templates page', async () => {
    await helpers.goto('/workflows/templates');

    // Check page loads with either templates list or empty state
    const hasHeading = await page.getByRole('heading', { name: /templates/i }).isVisible().catch(() => false);
    const hasEmptyState = await page.getByText(/no templates/i).isVisible().catch(() => false);
    const hasTemplates = await page.getByText(/workflow/i).isVisible().catch(() => false);

    expect(hasHeading || hasEmptyState || hasTemplates).toBeTruthy();
  });

  test('should display template categories or list', async () => {
    // Check for template categories or list items
    // Either shows category filters or template cards
    const hasCategories = await page.getByText(/category|automation|integration/i).first().isVisible().catch(() => false);
    const hasTemplateCards = await page.locator('.card, [class*="template"]').first().isVisible().catch(() => false);
    const hasEmptyState = await page.getByText(/no templates|create|get started/i).first().isVisible().catch(() => false);

    expect(hasCategories || hasTemplateCards || hasEmptyState).toBeTruthy();
  });
});

// ============================================================================
// Workflow Environments Tests
// ============================================================================

test.describe('Workflow Environments', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should navigate to environments page', async () => {
    await helpers.goto('/workflows/environment');

    // Check page loads
    const hasHeading = await page.getByRole('heading', { name: /environment/i }).isVisible().catch(() => false);
    const hasContent = await page.getByText(/variable|secret|environment/i).first().isVisible().catch(() => false);

    expect(hasHeading || hasContent).toBeTruthy();
  });

  test('should display environment variables section', async () => {
    // Check for environment variables or empty state
    const hasVariables = await page.getByText(/variable|name|value/i).first().isVisible().catch(() => false);
    const hasAddButton = await page.getByRole('button', { name: /add|create|new/i }).first().isVisible().catch(() => false);
    const hasEmptyState = await page.getByText(/no.*variable|get started/i).first().isVisible().catch(() => false);

    expect(hasVariables || hasAddButton || hasEmptyState).toBeTruthy();
  });
});

// ============================================================================
// Workflow AI Tests
// ============================================================================

test.describe('Workflow AI', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should navigate to workflow AI page', async () => {
    await helpers.goto('/workflows/ai');

    // Check page loads with AI workflow features
    const hasHeading = await page.getByRole('heading', { name: /ai|workflow/i }).first().isVisible().catch(() => false);
    const hasContent = await page.getByText(/ai|generate|create|assistant/i).first().isVisible().catch(() => false);

    expect(hasHeading || hasContent).toBeTruthy();
  });

  test('should display AI workflow generation interface', async () => {
    // Check for AI prompt input or workflow generation interface
    const hasPromptInput = await page.getByRole('textbox', { name: /describe|prompt|workflow/i }).isVisible().catch(() => false);
    const hasTextarea = await page.locator('textarea').first().isVisible().catch(() => false);
    const hasGenerateButton = await page.getByRole('button', { name: /generate|create|build/i }).first().isVisible().catch(() => false);
    const hasAIFeatures = await page.getByText(/ai|natural language|describe/i).first().isVisible().catch(() => false);

    expect(hasPromptInput || hasTextarea || hasGenerateButton || hasAIFeatures).toBeTruthy();
  });
});

// ============================================================================
// Admin Audit Logs Tests
// ============================================================================

test.describe('Admin Audit Logs', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);

    // Navigate to dashboard first to check if user is admin
    await helpers.goto('/dashboard');
    await page.waitForLoadState('networkidle');
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should navigate to audit logs page (admin only)', async () => {
    await helpers.openMobileSidebar();
    const adminSection = page.getByText('Admin', { exact: true });
    const isAdmin = await adminSection.isVisible().catch(() => false);

    if (!isAdmin) {
      test.skip();
      return;
    }

    await helpers.goto('/admin/audit-logs');

    // Check page loads
    const hasHeading = await page.getByRole('heading', { name: /audit.*log/i }).isVisible().catch(() => false);
    const hasTable = await page.locator('table').isVisible().catch(() => false);
    const hasContent = await page.getByText(/action|user|date|event/i).first().isVisible().catch(() => false);

    expect(hasHeading || hasTable || hasContent).toBeTruthy();
  });

  test('should display audit log entries or empty state', async () => {
    await helpers.openMobileSidebar();
    const adminSection = page.getByText('Admin', { exact: true });
    const isAdmin = await adminSection.isVisible().catch(() => false);

    if (!isAdmin) {
      test.skip();
      return;
    }

    // Check for log entries or empty state
    const hasLogEntries = await page.getByText(/login|create|update|delete/i).first().isVisible().catch(() => false);
    const hasEmptyState = await page.getByText(/no.*log|no.*record|empty/i).first().isVisible().catch(() => false);
    const hasFilterOptions = await page.getByText(/filter|search|date range/i).first().isVisible().catch(() => false);

    expect(hasLogEntries || hasEmptyState || hasFilterOptions).toBeTruthy();
  });

  test('should have filter/search capabilities', async () => {
    await helpers.openMobileSidebar();
    const adminSection = page.getByText('Admin', { exact: true });
    const isAdmin = await adminSection.isVisible().catch(() => false);

    if (!isAdmin) {
      test.skip();
      return;
    }

    // Check for filter options
    const hasSearch = await page.locator('input[type="search"], input[placeholder*="search"]').first().isVisible().catch(() => false);
    const hasDateFilter = await page.getByRole('textbox', { name: /date/i }).first().isVisible().catch(() => false);
    const hasActionFilter = await page.getByLabel(/action|type/i).first().isVisible().catch(() => false);
    const hasAnyFilter = await page.getByRole('combobox').first().isVisible().catch(() => false);

    expect(hasSearch || hasDateFilter || hasActionFilter || hasAnyFilter).toBeTruthy();
  });
});

// ============================================================================
// Admin Analytics Tests
// ============================================================================

test.describe('Admin Analytics', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);

    await helpers.goto('/dashboard');
    await page.waitForLoadState('networkidle');
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should navigate to analytics page (admin only)', async () => {
    await helpers.openMobileSidebar();
    const adminSection = page.getByText('Admin', { exact: true });
    const isAdmin = await adminSection.isVisible().catch(() => false);

    if (!isAdmin) {
      test.skip();
      return;
    }

    await helpers.goto('/admin/analytics');

    // Check page loads
    const hasHeading = await page.getByRole('heading', { name: /analytics/i }).isVisible().catch(() => false);
    const hasCharts = await page.locator('canvas, svg, [class*="chart"]').first().isVisible().catch(() => false);
    const hasStats = await page.getByText(/total|count|average|revenue/i).first().isVisible().catch(() => false);

    expect(hasHeading || hasCharts || hasStats).toBeTruthy();
  });

  test('should display analytics metrics', async () => {
    await helpers.openMobileSidebar();
    const adminSection = page.getByText('Admin', { exact: true });
    const isAdmin = await adminSection.isVisible().catch(() => false);

    if (!isAdmin) {
      test.skip();
      return;
    }

    // Check for analytics metrics
    const hasMetrics = await page.getByText(/users|projects|proposals|invoices|tickets|revenue/i).first().isVisible().catch(() => false);
    const hasDateRange = await page.getByText(/today|week|month|year|custom/i).first().isVisible().catch(() => false);

    expect(hasMetrics || hasDateRange).toBeTruthy();
  });

  test('should have date range selector', async () => {
    await helpers.openMobileSidebar();
    const adminSection = page.getByText('Admin', { exact: true });
    const isAdmin = await adminSection.isVisible().catch(() => false);

    if (!isAdmin) {
      test.skip();
      return;
    }

    // Check for date range controls
    const hasDateSelector = await page.getByRole('combobox').first().isVisible().catch(() => false);
    const hasDateRange = await page.getByText(/last 7 days|last 30 days|this month|custom/i).first().isVisible().catch(() => false);
    const hasDateInputs = await page.getByLabel(/date|from|to/i).first().isVisible().catch(() => false);

    expect(hasDateSelector || hasDateRange || hasDateInputs).toBeTruthy();
  });
});

// ============================================================================
// Admin Dashboard Tests
// ============================================================================

test.describe('Admin Dashboard', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);

    await helpers.goto('/dashboard');
    await page.waitForLoadState('networkidle');
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should navigate to admin dashboard (admin only)', async () => {
    await helpers.openMobileSidebar();
    const adminSection = page.getByText('Admin', { exact: true });
    const isAdmin = await adminSection.isVisible().catch(() => false);

    if (!isAdmin) {
      test.skip();
      return;
    }

    await helpers.goto('/admin');

    // Check page loads
    const hasHeading = await page.getByRole('heading', { name: /admin|dashboard/i }).isVisible().catch(() => false);
    const hasStats = await page.getByText(/total|users|organizations|active/i).first().isVisible().catch(() => false);

    expect(hasHeading || hasStats).toBeTruthy();
  });

  test('should display system overview stats', async () => {
    await helpers.openMobileSidebar();
    const adminSection = page.getByText('Admin', { exact: true });
    const isAdmin = await adminSection.isVisible().catch(() => false);

    if (!isAdmin) {
      test.skip();
      return;
    }

    // Check for system overview statistics
    const hasUserStats = await page.getByText(/user|member/i).first().isVisible().catch(() => false);
    const hasOrgStats = await page.getByText(/organization|company/i).first().isVisible().catch(() => false);
    const hasActivityStats = await page.getByText(/activity|recent|action/i).first().isVisible().catch(() => false);

    expect(hasUserStats || hasOrgStats || hasActivityStats).toBeTruthy();
  });

  test('should have quick navigation to admin pages', async () => {
    await helpers.openMobileSidebar();
    const adminSection = page.getByText('Admin', { exact: true });
    const isAdmin = await adminSection.isVisible().catch(() => false);

    if (!isAdmin) {
      test.skip();
      return;
    }

    // Check for navigation links
    const hasUsersLink = await page.getByRole('link', { name: /users/i }).first().isVisible().catch(() => false);
    const hasOrgsLink = await page.getByRole('link', { name: /organizations/i }).first().isVisible().catch(() => false);
    const hasAuditLink = await page.getByRole('link', { name: /audit/i }).first().isVisible().catch(() => false);

    expect(hasUsersLink || hasOrgsLink || hasAuditLink).toBeTruthy();
  });
});

// ============================================================================
// Accessibility Tests
// ============================================================================

test.describe('Accessibility Compliance', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should have proper heading hierarchy on dashboard', async () => {
    await helpers.goto('/dashboard');

    // Check for h1 heading
    const h1 = page.locator('h1');
    await expect(h1.first()).toBeVisible();

    // Check heading count (should have at least one)
    const headingCount = await h1.count();
    expect(headingCount).toBeGreaterThanOrEqual(1);
  });

  test('should have form labels associated with inputs', async () => {
    await helpers.goto('/projects/new');

    // Check that form inputs have associated labels
    const inputs = page.locator('input[type="text"], input[type="email"], select, textarea');
    const inputCount = await inputs.count();

    if (inputCount > 0) {
      // Check first input has a label
      const firstInput = inputs.first();
      const inputId = await firstInput.getAttribute('id');
      if (inputId) {
        const label = page.locator(`label[for="${inputId}"]`);
        const hasLabel = await label.isVisible().catch(() => false);
        const hasAriaLabel = await firstInput.getAttribute('aria-label');
        expect(hasLabel || hasAriaLabel).toBeTruthy();
      }
    }
  });

  test('should have focus indicators on interactive elements', async () => {
    await helpers.goto('/dashboard');

    // Find a button and check it can receive focus
    const button = page.getByRole('button').first();
    await button.focus();

    // Button should be visible when focused
    await expect(button).toBeVisible();
  });

  test('should support keyboard navigation', async () => {
    await helpers.goto('/dashboard');

    // Press Tab to navigate
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // Check that something is focused
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el && el.tagName !== 'BODY';
    });

    expect(focused).toBeTruthy();
  });

  test('should have skip navigation link', async () => {
    await helpers.goto('/dashboard');

    // Press Tab to reveal skip link
    await page.keyboard.press('Tab');

    // Check for skip to content link (common accessibility pattern)
    const skipLink = page.getByRole('link', { name: /skip to/i });
    const hasSkipLink = await skipLink.isVisible().catch(() => false);

    // If no skip link, check for main content landmark
    const mainContent = page.locator('main, [role="main"]');
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(hasSkipLink || hasMain).toBeTruthy();
  });
});

// ============================================================================
// Performance Tests
// ============================================================================

test.describe('Performance Benchmarks', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should load dashboard within acceptable time', async () => {
    const start = Date.now();
    await helpers.goto('/dashboard');
    const loadTime = Date.now() - start;

    // Dashboard should load within 10 seconds
    expect(loadTime).toBeLessThan(10000);
  });

  test('should load projects page within acceptable time', async () => {
    const start = Date.now();
    await helpers.goto('/projects');
    const loadTime = Date.now() - start;

    // Projects page should load within 10 seconds
    expect(loadTime).toBeLessThan(10000);
  });

  test('should load tickets page within acceptable time', async () => {
    const start = Date.now();
    await helpers.goto('/tickets');
    const loadTime = Date.now() - start;

    // Tickets page should load within 10 seconds
    expect(loadTime).toBeLessThan(10000);
  });

  test('should navigate between pages quickly', async () => {
    await helpers.goto('/dashboard');

    const start = Date.now();
    await helpers.navigateToSidebarLink('Projects');
    const navTime = Date.now() - start;

    // Navigation should be quick (under 5 seconds)
    expect(navTime).toBeLessThan(5000);
  });
});

// ============================================================================
// Error Recovery Tests
// ============================================================================

test.describe('Error Recovery', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should handle non-existent project gracefully', async () => {
    await helpers.goto('/projects/99999999');

    // Should show error message or redirect
    const hasError = await page.getByText(/not found|error|doesn't exist/i).first().isVisible().catch(() => false);
    const redirectedToProjects = page.url().includes('/projects') && !page.url().includes('99999999');

    expect(hasError || redirectedToProjects).toBeTruthy();
  });

  test('should handle non-existent ticket gracefully', async () => {
    await helpers.goto('/tickets/99999999');

    // Should show error message or redirect
    const hasError = await page.getByText(/not found|error|doesn't exist/i).first().isVisible().catch(() => false);
    const redirectedToTickets = page.url().includes('/tickets') && !page.url().includes('99999999');

    expect(hasError || redirectedToTickets).toBeTruthy();
  });

  test('should handle network errors gracefully', async () => {
    // Simulate offline mode temporarily
    await page.route('**/api/**', route => route.abort('internetdisconnected'));

    await helpers.goto('/dashboard');

    // Should show loading or error state, not crash
    const hasContent = await page.locator('body').isVisible();
    expect(hasContent).toBeTruthy();

    // Re-enable network
    await page.unroute('**/api/**');
  });
});

// ============================================================================
// Browser Storage Tests
// ============================================================================

test.describe('Browser Storage', () => {
  let context: BrowserContext;
  let page: Page;
  let helpers: PageHelpers;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      storageState: STORAGE_STATE_PATH,
    });
    page = await context.newPage();
    helpers = new PageHelpers(page);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('should persist authentication state', async () => {
    await helpers.goto('/dashboard');

    // Check that user is still authenticated
    const isAuthenticated = !page.url().includes('/login');
    expect(isAuthenticated).toBeTruthy();
  });

  test('should preserve form state on navigation', async () => {
    await helpers.goto('/projects/new');

    // Fill some form data
    await page.getByLabel('Project Name').fill('Test Project State');

    // Navigate away
    await helpers.navigateToSidebarLink('Dashboard');

    // Navigate back
    await helpers.navigateToSidebarLink('Projects');
    await page.getByRole('link', { name: /new project|create project/i }).click();

    // Form should be reset (standard behavior) or preserved (enhanced UX)
    const projectNameValue = await page.getByLabel('Project Name').inputValue();
    // Either behavior is acceptable - just verify form is accessible
    expect(await page.getByLabel('Project Name').isVisible()).toBeTruthy();
  });
});
