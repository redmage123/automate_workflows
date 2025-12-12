/**
 * Global Setup for Playwright E2E Tests
 *
 * WHAT: Setup script that runs before all tests.
 *
 * WHY: Ensures a clean test environment by:
 * - Clearing Redis rate limit keys to prevent 429 errors
 * - Performing authentication once and saving state
 * - Verifying backend and frontend are accessible
 *
 * HOW: Uses Redis client to delete rate limit keys, performs
 * login via Playwright to create authenticated storage state.
 */

import { createClient } from 'redis';
import { chromium, FullConfig } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const BACKEND_URL = process.env.BACKEND_URL || 'http://176.9.99.103:5000';
const FRONTEND_URL = process.env.BASE_URL || 'http://176.9.99.103:5101';
const TEST_USER_EMAIL = process.env.TEST_USER_EMAIL || 'braun.brelin@ai-elevate.ai';
const TEST_USER_PASSWORD = process.env.TEST_USER_PASSWORD || 'F00bar123!';

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Path to store authentication state
export const STORAGE_STATE_PATH = path.join(__dirname, '.auth', 'user.json');

async function globalSetup(config: FullConfig) {
  console.log('\n🔧 Running global setup...\n');

  // Clear Redis rate limit keys
  try {
    console.log('📦 Connecting to Redis...');
    const client = createClient({ url: REDIS_URL });
    await client.connect();

    // Find and delete all rate limit keys
    const keys = await client.keys('ratelimit:*');
    if (keys.length > 0) {
      console.log(`🗑️  Clearing ${keys.length} rate limit keys...`);
      await client.del(keys);
      console.log('✅ Rate limit keys cleared');
    } else {
      console.log('✅ No rate limit keys to clear');
    }

    await client.disconnect();
  } catch (error) {
    console.warn('⚠️  Could not connect to Redis (rate limits may affect tests):', error);
    // Don't fail setup if Redis is unavailable - tests will run but may hit rate limits
  }

  // Verify backend is accessible
  try {
    console.log('\n🔍 Checking backend availability...');
    const response = await fetch(`${BACKEND_URL}/api/health`);
    if (response.ok) {
      console.log('✅ Backend is available');
    } else {
      console.log(`⚠️  Backend returned status ${response.status}`);
    }
  } catch (error) {
    console.warn('⚠️  Backend may not be available:', error);
  }

  // Verify frontend is accessible
  try {
    console.log('\n🔍 Checking frontend availability...');
    const response = await fetch(FRONTEND_URL);
    if (response.ok) {
      console.log('✅ Frontend is available');
    } else {
      console.log(`⚠️  Frontend returned status ${response.status}`);
    }
  } catch (error) {
    console.warn('⚠️  Frontend may not be available:', error);
  }

  // Create authenticated state by logging in once
  console.log('\n🔐 Creating authenticated session...');

  // Ensure auth directory exists
  const authDir = path.dirname(STORAGE_STATE_PATH);
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  const browser = await chromium.launch();
  const page = await browser.newPage();

  try {
    await page.goto(`${FRONTEND_URL}/login`);
    await page.waitForLoadState('networkidle');

    // Fill login form
    await page.locator('#email').fill(TEST_USER_EMAIL);
    await page.locator('#password').fill(TEST_USER_PASSWORD);
    await page.getByRole('button', { name: /sign in/i }).click();

    // Wait for successful login
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    console.log('✅ Login successful');

    // Save storage state (cookies, localStorage)
    await page.context().storageState({ path: STORAGE_STATE_PATH });
    console.log(`✅ Saved auth state to ${STORAGE_STATE_PATH}`);
  } catch (error) {
    console.error('❌ Failed to create authenticated session:', error);
    // Don't fail - tests can try to login themselves
  } finally {
    await browser.close();
  }

  console.log('\n🚀 Setup complete, starting tests...\n');
}

export default globalSetup;
