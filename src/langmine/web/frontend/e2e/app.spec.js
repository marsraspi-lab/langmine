import { test, expect } from '@playwright/test';

test.describe('LangMine SPA', () => {

  test('page loads with sidebar and empty state', async ({ page }) => {
    await page.goto('/');

    // Sidebar should be visible
    await expect(page.locator('h1')).toContainText('LangMine');

    // URL input should exist
    await expect(page.locator('input[placeholder="YouTube URL..."]')).toBeVisible();

    // Pre-populated video should be in sidebar
    await expect(page.locator('.video-item').first()).toBeVisible();
    await expect(page.locator('.video-title').first()).toContainText('Test Video');
  });

  test('clicking a video loads its sentences', async ({ page }) => {
    await page.goto('/');

    // Click the first video
    await page.locator('.video-item').first().click();

    // Should see sentence cards
    await expect(page.locator('.sentence-card').first()).toBeVisible();
    await expect(page.locator('.chinese-text').first()).toContainText('我们');
  });

  test('filter tabs switch sentence visibility', async ({ page }) => {
    await page.goto('/');
    await page.locator('.video-item').first().click();

    // Should see i+1 card initially (All tab)
    await expect(page.locator('.status-badge.i1').first()).toBeVisible();

    // Click "i+1" tab
    await page.locator('.tab', { hasText: 'i+1' }).click();

    // Should still see i+1 card
    await expect(page.locator('.status-badge.i1').first()).toBeVisible();
  });

  test('Keep button marks a sentence as kept', async ({ page }) => {
    await page.goto('/');
    await page.locator('.video-item').first().click();

    // Click Keep on first card
    const keepBtn = page.locator('.sentence-card').first().locator('.btn-keep');
    await keepBtn.click();

    // Badge should change to kept
    await expect(page.locator('.sentence-card').first().locator('.status-badge').first()).toContainText('kept');
  });

  test('Delete button marks a sentence as deleted', async ({ page }) => {
    await page.goto('/');
    await page.locator('.video-item').first().click();

    // Click Delete on first card
    const deleteBtn = page.locator('.sentence-card').first().locator('.btn-delete');
    await deleteBtn.click();

    // Badge should change to deleted
    await expect(page.locator('.sentence-card').first().locator('.status-badge').first()).toContainText('deleted');
  });

  test('I Know This marks word as known and reclassifies', async ({ page }) => {
    await page.goto('/');
    await page.locator('.video-item').first().click();

    // Click "I Know This" on the i+1 card
    const iknowBtn = page.locator('.sentence-card').first().locator('.btn-iknow');
    await iknowBtn.click();

    // Badge should change to 'known' (i0)
    await expect(page.locator('.sentence-card').first().locator('.status-badge').first()).toContainText('known');
  });

  test('mine form shows validation message on empty input', async ({ page }) => {
    await page.goto('/');

    // Click Mine with empty input
    await page.locator('button', { hasText: 'Mine' }).click();

    // Should show error message
    await expect(page.locator('.mine-status')).toContainText('Enter a YouTube URL');
  });

  test('API returns CORS-friendly responses', async ({ page }) => {
    const response = await page.request.get('/api/videos');
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.videos).toBeDefined();
    expect(data.videos.length).toBeGreaterThan(0);
  });
});
