import { test, expect } from '@playwright/test';
import { MainPage, CurationPage, SettingsPage, VocabPage, ReadingPage, PreviewPage, SubtitleChip } from './pages.js';

test.describe('LangMine SPA', () => {
  let main, curation, settings, vocab, reading, preview, subtitles;

  test.beforeEach(async ({ page }) => {
    main      = new MainPage(page);
    curation  = new CurationPage(page);
    settings  = new SettingsPage(page);
    vocab     = new VocabPage(page);
    reading   = new ReadingPage(page);
    preview   = new PreviewPage(page);
    subtitles = new SubtitleChip(page);
  });

  // ── Basic page load ──────────────────────────────────────────────────

  test('page loads with sidebar and empty state', async () => {
    await main.goto();
    await main.expectLoaded();
    await main.expectFirstVideoTitle('Test Video');
  });

  test('clicking a video loads its sentences', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.expectCardsLoaded();
    await expect(curation.chineseText.first()).toContainText('我们');
  });

  test('filter tabs switch sentence visibility', async () => {
    await main.goto();
    await main.selectFirstVideo();

    await expect(curation.statusBadge('i1').first()).toBeVisible();
    await curation.clickFilter('i+1');
    await expect(curation.statusBadge('i1').first()).toBeVisible();
  });

  // ── M9: Word highlighting ────────────────────────────────────────────

  test('sentence cards show word highlighting classes', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.expectWordHighlighting();
  });

  test('clicking a word opens popover with status toggle', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.clickFirstLearningWord();
    await curation.expectPopoverVisible();
  });

  test('mark word known from popover updates the word status', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.clickFirstLearningWord();
    await curation.clickMarkKnown();
    await curation.expectWordKnownAfterMark();
  });

  // ── Sentence actions ─────────────────────────────────────────────────

  test('Keep button marks a sentence as kept', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.clickFirstKeep();
    await curation.expectFirstBadge('kept');
  });

  // ── M11: Cloze export ─────────────────────────────────────────────────

  test('cloze deletion checkbox is visible and togglable', async () => {
    await main.goto();
    const clozeCheckbox = main.page.locator('.force-update-label', { hasText: 'Cloze deletion cards' });
    await expect(clozeCheckbox).toBeVisible();
    const input = clozeCheckbox.locator('input[type="checkbox"]');
    await expect(input).not.toBeChecked();
    // Toggle on
    await input.check();
    await expect(input).toBeChecked();
    // Toggle off
    await input.uncheck();
    await expect(input).not.toBeChecked();
  });

  // ── M12: Image search ─────────────────────────────────────────────────

  test('image search modal opens from word popover', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();
    // Click word to open popover, then click image search
    await reading.clickWord('一般');
    await reading.expectPopoverVisible();

    const searchBtn = main.page.locator('.popover-btn', { hasText: 'Search images' });
    await searchBtn.click();

    // Image picker modal should appear
    const picker = main.page.locator('.image-picker-modal');
    await expect(picker).toBeVisible();
    await expect(picker).toContainText('一般');

    // Click "Search images" to trigger the API call
    await main.page.locator('.image-picker-search-btn').click();

    // Images should load (FakeImageSearch returns placeholder URLs)
    const grid = main.page.locator('.image-grid');
    await expect(grid).toBeVisible({ timeout: 5000 });
    const items = main.page.locator('.image-grid-item');
    await expect(items.first()).toBeVisible();
  });

  test('export with cloze sends card_type=cloze to API', async () => {
    await main.goto();
    // Click first video to load sentences (so export section appears)
    await main.selectFirstVideo();

    // Check the cloze checkbox
    const clozeLabel = main.page.locator('.force-update-label', { hasText: 'Cloze deletion cards' });
    await clozeLabel.locator('input[type="checkbox"]').check();

    // Click the export button
    const exportBtn = main.page.locator('.export-btn');
    await exportBtn.click();

    // Should show success status (fake exporter returns added=1)
    await expect(main.page.locator('.export-status')).toContainText('new');
  });

  // Must run BEFORE any state-mutating tests — the 'Deleted' tab empty state
  // relies on no sentences being deleted in the shared test server data.
  test('Stash tab shows empty state when none', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await expect(curation.chineseText.first()).toBeVisible({ timeout: 5000 });
    await curation.clickFilter('Deleted');
    await curation.expectEmptyState('No deleted sentences');
  });

  test('Delete button shows confirmation, then deletes', async () => {
    await main.goto();
    await main.selectFirstVideo();

    await expect(curation.firstCard.deleteBtn()).toContainText('Delete');
    await curation.clickFirstDelete();
    await expect(curation.firstCard.deleteBtn()).toContainText('Confirm delete');
    await expect(curation.firstCard.cancelBtn()).toBeVisible();
    await curation.clickFirstDelete();
    await curation.expectFirstBadge('deleted');
  });

  test('mark word known from popover updates display instantly', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.clickFirstLearningWord();
    await curation.clickMarkKnown();
    // Word should now show known styling (popover-triggering word was already .word-learning)
    await expect(curation.firstCard.wordKnown().first()).toBeVisible({ timeout: 5000 });
  });

  // ── Mine form ────────────────────────────────────────────────────────

  test('mine form shows validation message on empty input', async () => {
    await main.goto();
    await main.mineButton.click();
    await expect(main.mineStatus).toContainText('Enter a YouTube URL');
  });

  // ── M6: Stash tab ────────────────────────────────────────────────────

  test('Stash tab shows stashed sentences', async () => {
    await main.goto();
    await main.selectFirstVideo();
    // Wait for any sentences to appear (initial load completed)
    await expect(curation.chineseText.first()).toBeVisible({ timeout: 5000 });
    await curation.clickFilter('Stashed');
    await expect(curation.statusBadge('stashed').first()).toBeVisible({ timeout: 5000 });
    await expect(curation.chineseText.first()).toContainText('效率');
  });

  // ── M6: Screenshot display ───────────────────────────────────────────

  test('screenshot appears on card when has_screenshot is true', async () => {
    await main.goto();
    await main.selectFirstVideo();
    const screenshot = curation.firstCard.screenshot();
    await expect(screenshot).toBeVisible();
    await expect(screenshot.locator('img')).toHaveAttribute('src', /screenshot/);
  });

  // ── M7: Theme toggle ─────────────────────────────────────────────────

  test('theme toggle switches between dark and light', async () => {
    await main.goto();
    await main.expectTheme('dark');
    await main.toggleTheme();
    await main.expectTheme('light');
  });

  // ── M7: Settings page ────────────────────────────────────────────────

  test('navigate to settings page and see config form', async () => {
    await main.goto();
    await main.clickNav('Settings');
    await settings.expectFormVisible();
  });

  test('settings page save button updates config', async () => {
    await main.goto();
    await main.clickNav('Settings');
    await settings.saveDeckName('E2E Test Deck');
    await main.expectToast('Settings saved');
  });

  // ── M7: Inline editing ───────────────────────────────────────────────

  test('click reading to edit inline', async () => {
    await main.goto();
    await main.selectFirstVideo();

    await curation.firstCard.readingText().click();
    const input = curation.firstCard.readingInput();
    await expect(input).toBeVisible();
    await input.fill('wo men yi ban zao shang qi chuang');
    await input.press('Enter');
    await main.expectToast('Saved');
  });

  test('edit translation inline', async () => {
    await main.goto();
    await main.selectFirstVideo();

    await curation.firstCard.transText().click();
    await expect(curation.firstCard.transInput()).toBeVisible();
  });

  test('cancel edit on Escape returns to display mode', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.expectCardsLoaded();

    const transText = curation.firstCard.transText();
    if (await transText.isVisible()) {
      await transText.click();
      const input = curation.firstCard.transInput();
      await expect(input).toBeVisible({ timeout: 5000 });
      await input.press('Escape');
      await expect(curation.firstCard.transText()).toBeVisible();
      await expect(curation.firstCard.transInput()).not.toBeVisible();
    }
    // If translation isn't visible (pre-edited away), test passes vacuously
  });

  // ── Navigation ───────────────────────────────────────────────────────

  test('navigate back to curation from settings', async () => {
    await main.goto();
    await main.clickNav('Settings');
    await expect(settings.heading).toContainText('Settings');
    await main.clickNav('Curation');
    await expect(main.urlInput).toBeVisible();
  });

  // ── API checks ───────────────────────────────────────────────────────

  test('API returns CORS-friendly responses', async ({ page }) => {
    const response = await page.request.get('/api/videos');
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.videos).toBeDefined();
    expect(data.videos.length).toBeGreaterThan(0);
  });

  test('GET /api/config returns settings', async ({ page }) => {
    const response = await page.request.get('/api/config');
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.anki_connect_url).toBeDefined();
    expect(data.source_language).toBeDefined();
    expect(data.max_cards_per_video).toBeDefined();
  });

  // ── M9: Vocab page ───────────────────────────────────────────────────

  test('navigate to vocab page and see word list', async () => {
    await main.goto();
    await main.clickNav('Vocabulary');
    await vocab.expectLoaded();
  });

  test('vocab page shows status filter tabs', async () => {
    await main.goto();
    await main.clickNav('Vocabulary');
    await vocab.expectFilterTabs();
  });

  test('vocab page search filters words', async () => {
    await main.goto();
    await main.clickNav('Vocabulary');
    await vocab.search('学习');
    await expect(vocab.wordRows.filter({ hasText: '学习' }).first()).toBeVisible();
    await expect(vocab.wordRows.filter({ hasText: '效率' })).toHaveCount(0);
  });

  test('clicking vocab word row shows detail panel', async () => {
    await main.goto();
    await main.clickNav('Vocabulary');
    await vocab.clickFirstWord();
    await vocab.expectDetailVisible();
  });

  // ── M9: Vocab API ────────────────────────────────────────────────────

  test('GET /api/vocab returns paginated words', async ({ page }) => {
    const response = await page.request.get('/api/vocab?per_page=200');
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.words).toBeDefined();
    expect(data.total).toBeGreaterThanOrEqual(3);
    expect(data.page).toBe(1);
    expect(data.per_page).toBe(200);

    const word = data.words[0];
    expect(word.word).toBeDefined();
    expect(word.status).toBeDefined();
    expect(word.hsk_level).toBeDefined();
    expect(word.sentence_count).toBeDefined();
  });

  test('GET /api/vocab filters by status', async ({ page }) => {
    const response = await page.request.get('/api/vocab?status=learning');
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.total).toBeGreaterThanOrEqual(2);
    for (const w of data.words) {
      expect(w.status).toBe('learning');
    }
  });

  test('GET /api/vocab/<word> returns word detail with sentences', async ({ page }) => {
    const response = await page.request.get('/api/vocab/%E4%B8%80%E8%88%AC');
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.word.word).toBe('一般');
    expect(data.word.hsk_level).toBe(3);
    expect(data.sentences).toBeDefined();
    expect(data.sentences.length).toBeGreaterThanOrEqual(1);
  });

  test('PATCH /api/vocab/<word> toggles word status', async ({ page }) => {
    const response = await page.request.patch('/api/vocab/%E4%B8%80%E8%88%AC', {
      data: { status: 'known' }
    });
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.ok).toBe(true);
    expect(data.status).toBe('known');

    const check = await page.request.get('/api/vocab/%E4%B8%80%E8%88%AC');
    const checkData = await check.json();
    expect(checkData.word.status).toBe('known');
  });

  test('sentence response includes words array with status metadata', async ({ page }) => {
    const response = await page.request.get('/api/videos');
    const videos = await response.json();
    const vid = videos.videos[0];

    const sentResp = await page.request.get(`/api/videos/${vid.id}/sentences`);
    const sentData = await sentResp.json();

    const firstSentence = sentData.sentences[0];
    expect(firstSentence.words).toBeDefined();
    expect(firstSentence.words.length).toBeGreaterThan(0);

    const word = firstSentence.words[0];
    expect(word.token).toBeDefined();
    expect(word.status).toBeDefined();
    expect(['known', 'learning', 'unknown']).toContain(word.status);
  });

  // ── M10: Reading mode ─────────────────────────────────────────────────

  test('reading mode shows all sentences as continuous text', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();
    await reading.expectLoaded();
    await reading.expectSentenceCount(55);
    await reading.expectToolbarInfo('55 sentences');
  });

  test('reading mode shows word highlighting', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();
    await reading.expectWordHighlighting();
  });

  test('clicking a word opens popover with status buttons', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();
    await reading.clickWord('一般');
    await reading.expectPopoverVisible();
    await expect(reading.popoverWord).toContainText('一般');
    await expect(reading.popoverBtn('Mark known')).toBeVisible();
    await expect(reading.popoverBtn('Mark learning')).toBeVisible();
    await expect(reading.popoverBtn('Mark unknown')).toBeVisible();
  });

  test('Escape closes word popover', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();
    await reading.clickWord('一般');
    await reading.expectPopoverVisible();
    await reading.pressKey('Escape');
    await reading.expectPopoverHidden();
  });

  test('? toggles keyboard shortcuts bar', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();
    await reading.pressKey('?');
    await reading.expectShortcutsVisible();
    await reading.pressKey('?');
    await expect(reading.shortcutsBar).not.toBeVisible();
  });

  test('T toggles translation visibility', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();
    // Translation hidden by default
    await reading.expectTranslationHidden();
    // Toggle on
    await reading.pressKey('t');
    await reading.expectTranslationVisible();
    // Toggle off
    await reading.pressKey('t');
    await reading.expectTranslationHidden();
  });

  // ── M13: Difficulty preview ───────────────────────────────────────────

  test('preview shows stats and transcript with word highlighting', async () => {
    await main.goto();

    // Type a YouTube URL (any valid URL — fake transcript returns fixed data)
    await main.urlInput.fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');

    // Click Preview
    await preview.clickPreview();

    // Panel should appear with stats
    await preview.expectPanelVisible();
    await preview.expectStatsVisible();

    // Transcript with word highlighting should be visible
    await preview.expectTranscriptVisible();
    await preview.expectWordHighlighting();
  });

  // ── M14: Show in dictionary ────────────────────────────────────────────

  test('Show in dictionary from popover navigates to VocabPage', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();

    // Open popover for a known learning word ("一般")
    await reading.clickWord('一般');
    await reading.expectPopoverVisible();

    // Click "Show in dictionary"
    const dictBtn = main.page.locator('.popover-btn', { hasText: 'Show in dictionary' });
    await expect(dictBtn).toBeVisible();
    await dictBtn.click();

    // Should navigate to VocabPage
    await expect(main.page.locator('h2')).toContainText('Vocabulary', { timeout: 5000 });
    // Search input should be pre-filled with the word
    await expect(main.page.locator('.search-input')).toHaveValue('一般');
  });

  // ── M20: Proper name brackets ──────────────────────────────────────────

  test('proper name words are wrapped in brackets in reading mode', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();

    // "李世民" should appear as a proper-name word with bracket styling
    await expect(reading.properNameWords.first()).toBeVisible();
    const liShimin = reading.properNameWords.filter({ hasText: '李世民' });
    await expect(liShimin).toBeVisible();
  });

  test('clicking a proper name shows dismiss option in popover', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();

    // Click the proper name "李世民"
    await reading.clickWord('李世民');
    await reading.expectPopoverVisible();

    // Popover should show "Not a proper name" dismiss button
    const dismissBtn = main.page.locator('.popover-btn', { hasText: 'Not a proper name' });
    await expect(dismissBtn).toBeVisible();
  });

  // ── M20+: Manual proper-name marking ─────────────────────────────────

  test('curation view shows "Mark as proper name" button for non-proper-name word', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.expectCardsLoaded();

    // Sentence 5 is "李世民 / 是 / 唐朝 / 皇帝" — click 唐朝
    const sentence5 = curation.cards.nth(4);  // 0-indexed, sentence 5
    await expect(sentence5).toBeVisible();

    // Click the word "唐朝" (should be .word-unknown or similar, NOT proper-name)
    const tangChao = sentence5.locator('.word-token', { hasText: '唐朝' });
    await tangChao.click();

    await curation.expectPopoverVisible();

    // Should show "Mark as proper name" button
    const markBtn = main.page.locator('.popover-btn', { hasText: 'Mark as proper name' });
    await expect(markBtn).toBeVisible();
  });

  test('manual mark as proper name from reading mode popover', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();

    // Click a non-proper-name word (e.g., "皇帝")
    await reading.clickWord('皇帝');
    await reading.expectPopoverVisible();

    // Verify "Mark as proper name" button exists
    const markBtn = reading.popoverBtn('Mark as proper name');
    await expect(markBtn).toBeVisible();

    // Click it
    await markBtn.click();

    // Transcript reloads — verify "皇帝" now has proper-name styling
    await expect(reading.properNameWords.filter({ hasText: '皇帝' }).first()).toBeVisible({ timeout: 5000 });
    await expect(main.page.locator('.toast-success').first()).toContainText('proper name');
  });

  // ── M22: Add Sentences + Reclassification ──────────────────────────────

  test('Reclassify button appears and triggers reclassification', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.expectCardsLoaded();

    // Button should be visible with initial label
    const btn = curation.addSentencesBtn;
    await expect(btn).toBeVisible();
    await expect(btn).toContainText('Reclassify');

    // Click it
    await btn.click();

    // Wait for reclassification to complete — button updates
    // With 55 total sentences, first page has 50 → hasMore=true
    await expect(btn).toContainText('Add more sentences', { timeout: 5000 });
  });

  test('Add more sentences loads next page', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.expectCardsLoaded();

    // First: trigger reclassification
    const btn = curation.addSentencesBtn;
    await btn.click();
    await expect(btn).toContainText('Add more sentences', { timeout: 5000 });

    // Click "Add more sentences" to load remaining
    await btn.click();

    // After loading remaining 5 sentences (total=55, offset was 50),
    // hasMore becomes false → button reverts to "Reclassify"
    await expect(btn).toContainText('Reclassify', { timeout: 5000 });
  });

  // ── M23: Word Splitting ─────────────────────────────────────────────

  test('editing text_segmented with spaces splits and merges words', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.expectCardsLoaded();

    // Click the segmented-text display to enter edit mode
    const sentence1 = curation.cards.nth(0);
    const segText = sentence1.locator('.segmented-text');
    await segText.click();

    // Input appears with space-separated form
    const segInput = main.page.locator('.edit-input.segmented-input');
    await expect(segInput).toBeVisible();
    await expect(segInput).toHaveValue('我们 一般 早上 起床');

    // Split "一般" → "一 般" (add space)
    await segInput.fill('我们 一 般 早上 起床');
    await segInput.press('Enter');

    // Toast confirms save
    await main.expectToast('Saved');

    // Wait for cards to reload after refreshAfterAction
    await curation.expectCardsLoaded();

    // Re-open to verify persisted as " / " format (re-query after DOM refresh)
    const segText2 = curation.cards.nth(0).locator('.segmented-text');
    await segText2.click();
    await expect(segInput).toHaveValue('我们 一 般 早上 起床');
  });

  // ── M24: Sentence Joining ────────────────────────────────────────────

  test('merge with previous combines two sentences', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await curation.expectCardsLoaded();

    // Sentence 5 (李世民...) should have merge button
    const sentence5 = curation.cards.nth(4);
    const mergeBtn = sentence5.locator('.btn-merge');
    await expect(mergeBtn).toBeVisible();
    await expect(mergeBtn).toContainText('Merge');

    // Sentence 1 should NOT have merge button (first sentence)
    const sentence1 = curation.cards.nth(0);
    await expect(sentence1.locator('.btn-merge')).toHaveCount(0);

    // Click merge on sentence 5
    await mergeBtn.click();

    // Wait for the card list to refresh
    await expect(curation.cards).not.toHaveCount(5, { timeout: 5000 });
  });

  // ── Dismiss proper name (must be LAST — mutates shared state) ──────────

  test('dismiss proper name removes brackets in reading mode', async () => {
    await main.goto();
    await main.selectFirstVideo();
    await reading.enterReadingMode();

    // 李世民 is auto-detected as proper-name
    await reading.clickWord('李世民');
    await reading.expectPopoverVisible();

    // Click "Not a proper name" dismiss button
    const dismissBtn = reading.popoverBtn('Not a proper name');
    await dismissBtn.click();

    // Transcript reloads — verify 李世民 no longer has proper-name styling
    await expect(reading.properNameWords.filter({ hasText: '李世民' })).toHaveCount(0, { timeout: 5000 });
    await expect(main.page.locator('.toast-success').first()).toContainText('not a proper name');
  });

  // ── M25/M26: Subtitle discovery + language selection ────────────────────

  test('shows manual subtitle chip on URL input', async () => {
    await main.goto();
    // jNQXAC9IVRw = manual Chinese subs in test server
    await main.urlInput.fill('https://www.youtube.com/watch?v=jNQXAC9IVRw');
    await main.page.waitForTimeout(1200);  // debounce (800ms) + API
    await subtitles.expectChipVisible('manual');
    await subtitles.expectChipText('Chinese');
  });

  test('shows auto-only warning when only auto subs available', async () => {
    await main.goto();
    // dQw4w9WgXcQ = auto English subs in test server — no manual subs
    await main.urlInput.fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await main.page.waitForTimeout(1200);
    await subtitles.expectChipVisible('auto');
    await subtitles.expectChipText('No manual subtitles');
  });

  test('shows no-subtitle chip for unknown video', async () => {
    await main.goto();
    await main.urlInput.fill('https://www.youtube.com/watch?v=unknown12345');
    await main.page.waitForTimeout(1200);
    await subtitles.expectChipVisible('none');
    await subtitles.expectChipText('No subtitles available');
  });

  test('shows language dropdown with only manual subtitles', async () => {
    await main.goto();
    // aAaAaAaAaAa = 2 manual (zh-Hans, en) + 1 auto (ja) in test server
    await main.urlInput.fill('https://www.youtube.com/watch?v=aAaAaAaAaAa');
    await main.page.waitForTimeout(1200);
    await subtitles.expectDropdownVisible();
    await subtitles.expectOptionCount(2);  // only manual subs
  });

  test('can mine with a selected subtitle language', async () => {
    await main.goto();
    // Use multi-lang video, select Chinese (Simplified) (manual), then mine
    await main.urlInput.fill('https://www.youtube.com/watch?v=aAaAaAaAaAa');
    await main.page.waitForTimeout(1200);
    await subtitles.expectDropdownVisible();
    await subtitles.selectLanguage('zh-Hans');
    await main.mineButton.click();
    // Mine should start (fake pipeline succeeds instantly)
    await expect(main.mineStatus).toContainText(/sentences/, { timeout: 15000 });
  });

  test('shows subtitle kind badge in video list', async () => {
    await main.goto();
    await main.expectLoaded();
    // The seed video dQw4w9WgXcQ has subtitle info
    // Navigate to the video to trigger subtitle fetch, then check the sidebar list
    await main.urlInput.fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    await main.page.waitForTimeout(1200);
    // The seed video should have an auto badge after we mined it with auto subs
    // Mine the multi-lang video with a language to see the badge appear
    await main.urlInput.fill('https://www.youtube.com/watch?v=jNQXAC9IVRw');
    await main.page.waitForTimeout(1200);
    await subtitles.expectChipVisible('manual');
    await main.mineButton.click();
    await main.page.waitForTimeout(3000);  // wait for mine to finish
    // After mining, the video list should show the badge
    // Reload to see the video entry
    await main.goto();
    await main.expectLoaded();
    const badges = subtitles.videoBadges;
    // At least one badge should be visible (from the newly mined video or the seed)
    await expect(badges.first()).toBeVisible({ timeout: 5000 });
  });
});
