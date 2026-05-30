import { expect } from '@playwright/test';

/**
 * Page objects for LangMine E2E tests.
 *
 * Each class wraps a page/view with its locators and common actions.
 * Tests compose these instead of repeating raw .locator() calls.
 */

// ── Main page (sidebar, video list, nav) ───────────────────────────────

export class MainPage {
  constructor(page) {
    this.page = page;
  }

  // Locators
  get title()         { return this.page.locator('h1'); }
  get urlInput()      { return this.page.locator('input[placeholder="YouTube URL..."]'); }
  get videoItems()    { return this.page.locator('.video-item'); }
  get videoTitles()   { return this.page.locator('.video-title'); }
  get mineButton()    { return this.page.getByRole('button', { name: 'Mine' }); }
  get mineStatus()    { return this.page.locator('.mine-status'); }
  get themeBtn()      { return this.page.locator('.theme-btn'); }
  get html()          { return this.page.locator('html'); }
  get toast()         { return this.page.locator('.toast-success').first(); }

  navButton(label)    { return this.page.locator('.nav-btn', { hasText: label }); }

  // Actions
  async goto() {
    await this.page.goto('/');
  }

  async selectFirstVideo() {
    await this.videoItems.first().click();
  }

  async clickNav(label) {
    await this.navButton(label).click();
  }

  async toggleTheme() {
    await this.themeBtn.click();
  }

  // Assertions
  async expectLoaded() {
    await expect(this.title).toContainText('LangMine');
    await expect(this.urlInput).toBeVisible();
    await expect(this.videoItems.first()).toBeVisible();
  }

  async expectFirstVideoTitle(text) {
    await expect(this.videoTitles.first()).toContainText(text);
  }

  async expectTheme(value) {
    await expect(this.html).toHaveAttribute('data-theme', value);
  }

  async expectToast(text) {
    await expect(this.toast).toContainText(text);
  }
}

// ── Curation area (sentence cards, filter tabs, word interactions) ─────

export class CurationPage {
  constructor(page) {
    this.page = page;
  }

  // Locators
  get cards()              { return this.page.locator('.sentence-card'); }
  get chineseText()        { return this.page.locator('.chinese-text'); }
  get emptyState()         { return this.page.locator('.empty-state'); }
  get wordPopover()        { return this.page.locator('.word-popover'); }

  /** First card helpers */
  firstCard = {
    locator:      () => this.cards.first(),
    keepBtn:      () => this.cards.first().locator('.btn-keep'),
    deleteBtn:    () => this.cards.first().locator('.btn-delete'),
    cancelBtn:    () => this.cards.first().locator('.btn-cancel'),
    iknowBtn:     () => this.cards.first().locator('.btn-iknow'),
    statusBadge:  () => this.cards.first().locator('.status-badge').first(),
    wordKnown:    () => this.cards.first().locator('.word-known'),
    wordLearning: () => this.cards.first().locator('.word-learning'),
    pinyinText:   () => this.cards.first().locator('.pinyin-text'),
    pinyinInput:  () => this.cards.first().locator('.pinyin-input'),
    transText:    () => this.cards.first().locator('.translation-text'),
    transInput:   () => this.cards.first().locator('.translation-input'),
    screenshot:   () => this.cards.first().locator('.screenshot-thumb'),
  };

  statusBadge(type)       { return this.page.locator(`.status-badge.${type}`); }
  filterTab(label)        { return this.page.locator('.tab', { hasText: label }); }

  // Actions
  async clickFilter(label) {
    await this.filterTab(label).click();
  }

  async clickFirstKeep()         { await this.firstCard.keepBtn().click(); }
  async clickFirstDelete()       { await this.firstCard.deleteBtn().click(); }
  async clickFirstIKnowThis()    { await this.firstCard.iknowBtn().click(); }
  async clickFirstLearningWord() { await this.firstCard.wordLearning().first().click(); }
  async clickMarkKnown()         { await this.page.locator('.word-popover .btn-mark-known').click(); }

  // Assertions
  async expectCardsLoaded() {
    await expect(this.cards.first()).toBeVisible();
    await expect(this.chineseText.first()).toBeVisible({ timeout: 10000 });
  }

  async expectFirstBadge(text) {
    await expect(this.firstCard.statusBadge()).toContainText(text);
  }

  async expectWordHighlighting() {
    await expect(this.firstCard.wordKnown().first()).toBeVisible();
    await expect(this.firstCard.wordLearning().first()).toBeVisible();
    await expect(this.firstCard.wordLearning().first()).toContainText('一般');
  }

  async expectPopoverVisible() {
    await expect(this.wordPopover).toBeVisible();
    await expect(this.wordPopover).toContainText('Mark known');
  }

  async expectWordKnownAfterMark() {
    await expect(this.firstCard.wordKnown().filter({ hasText: '一般' })).toBeVisible();
  }

  async expectEmptyState(text) {
    await expect(this.emptyState).toContainText(text);
  }
}

// ── Settings page ──────────────────────────────────────────────────────

export class SettingsPage {
  constructor(page) {
    this.page = page;
  }

  get heading()          { return this.page.locator('h2'); }
  get deckNameInput()    { return this.page.locator('input[name="deck_name"]'); }
  get maxCardsInput()    { return this.page.locator('input[name="max_cards_per_video"]'); }
  get saveBtn()          { return this.page.locator('.save-btn'); }

  async expectFormVisible() {
    await expect(this.heading).toContainText('Settings');
    await expect(this.deckNameInput).toBeVisible();
    await expect(this.maxCardsInput).toBeVisible();
  }

  async saveDeckName(name) {
    await this.deckNameInput.fill(name);
    await this.saveBtn.click();
  }
}

// ── Vocab page ─────────────────────────────────────────────────────────

export class VocabPage {
  constructor(page) {
    this.page = page;
  }

  get heading()       { return this.page.locator('h2'); }
  get wordRows()      { return this.page.locator('.word-row'); }
  get searchInput()   { return this.page.locator('.search-input'); }
  get wordDetail()    { return this.page.locator('.word-detail'); }
  get detailWord()    { return this.page.locator('.detail-word'); }

  filterTab(label)    { return this.page.locator('.filter-tab', { hasText: label }); }

  async expectLoaded() {
    await expect(this.heading).toContainText('Vocabulary');
    await expect(this.wordRows.first()).toBeVisible();
  }

  async expectFilterTabs() {
    await expect(this.filterTab('All')).toBeVisible();
    await expect(this.page.locator('.filter-tab').filter({ hasText: /^🟢 Known$/ })).toBeVisible();
    await expect(this.page.locator('.filter-tab').filter({ hasText: /^🟡 Learning$/ })).toBeVisible();
  }

  async search(text) {
    await this.searchInput.fill(text);
  }

  async clickFirstWord() {
    await this.wordRows.first().click();
  }

  async expectDetailVisible() {
    await expect(this.wordDetail).toBeVisible();
    await expect(this.detailWord).toBeVisible();
  }
}
