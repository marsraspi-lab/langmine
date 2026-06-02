import { test as base } from '@playwright/test';

/**
 * Custom test fixture that catches uncaught JS errors and
 * fails the test immediately instead of silently timing out.
 *
 * Catches: pageerror (uncaught exceptions + unhandled rejections)
 *           console.error (explicit error logging)
 */

export const test = base.extend({
  page: async ({ page }, use) => {
    const errors = [];

    page.on('pageerror', (err) => {
      errors.push(err.message);
    });

    // Also catch console.error calls — these often precede a crash
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await use(page);

    if (errors.length > 0) {
      throw new Error(
        `Uncaught JS errors on page:\n  - ${errors.join('\n  - ')}`
      );
    }
  },
});

export { expect } from '@playwright/test';
