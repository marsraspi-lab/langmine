# LangMine Acceptance Test Checklist — M0–M18

> Manual QA checklist. Run through these in order after a fresh deploy.
> Each item is one observable pass/fail check. UI and API tests only.

---

## M0–M2: Mine, Classify, Pipeline

- [ ] **Mine succeeds** — paste URL in web UI, mining starts, progress updates appear
- [ ] **Pipeline produces output** — `data/` directory fills with `.mp3` audio clips per sentence
- [ ] **i+1 classifier runs** — sentences are classified (known=1-unknown, learnable=i+1, too-hard=i+2+)
- [ ] **HSK bootstrap works** — words in HSK 1–3 are treated as "known" by default

---

## M3: Curate in Browser (Web UI)

- [ ] **App loads** — `langmine` → `http://localhost:8080` shows sidebar + empty state
- [ ] **Sidebar shows video list** — mined videos appear in the left sidebar
- [ ] **Click video loads sentences** — selecting a video populates the card list
- [ ] **Filter tabs work** — All / i+1 / Kept / Deleted / Stash tabs show correct sentence subsets
- [ ] **Keep button** — clicking Keep moves sentence to Kept filter, updates status badge
- [ ] **Delete button** — shows confirmation prompt, then moves sentence to Deleted
- [ ] **Empty state** — each tab shows a message when no sentences match

---

## M4: Translate & Understand (NLP)

- [ ] **Chinese segmentation** — sentences show segmented words (spaces between tokens)
- [ ] **Reading displayed** — each sentence card shows reading (pinyin) below the Chinese text
- [ ] **Translation displayed** — each sentence card shows German (target language) translation
- [ ] **Frequency badge** — unknown words show frequency rank and tier icon (🔥/⭐/💎)
- [ ] **HSK level badge** — known words show HSK level when available

---

## M5: Export to Anki

- [ ] **Web UI export button** — "📦 Export to Anki" button in sidebar triggers export
- [ ] **Update card templates** — checking "⚡ Update card templates" in sidebar pushes template changes from language extension
- [ ] **Cards appear in Anki** — deck "Chinese::Sentence Mining" receives cards with audio + translation

---

## M6: Stash & Screenshots

- [ ] **Stash tab** — shows i+2+ sentences in descending score order
- [ ] **Stash empty state** — shows message when no stashed sentences
- [ ] **Stash sentences are kept** — clicking Keep on a stash sentence moves it to Kept
- [ ] **Screenshots captured** — sentence cards show a frame from the video at the sentence timestamp
- [ ] **Screenshot in Anki** — exported cards include the screenshot on the back

---

## M7: Polish & Edit

- [ ] **Inline reading edit** — click reading text on a card → input field → edit → save persists
- [ ] **Inline translation edit** — click translation → edit → save persists
- [ ] **Cancel edit (Escape)** — pressing Escape during inline edit returns to display mode
- [ ] **Settings page** — gear icon opens Settings page with config form
- [ ] **Settings save** — changing a value and clicking Save updates `config.yaml` (toast confirms)
- [ ] **Dark/light theme toggle** — theme switch toggles between dark and light mode
- [ ] **Theme persists** — refreshing the page keeps the selected theme
- [ ] **Validation on empty input** — mine form shows error when submitted with empty URL

---

## M8: Docker Deployment

- [ ] **docker compose up** — `docker compose up` starts the app on port 8080
- [ ] **AnkiConnect reachable** — export to Anki works from inside Docker (`host.docker.internal`)
- [ ] **docker run** — single `docker run` command starts the app
- [ ] **Build from source** — `docker build --build-arg VERSION=1.5.0 -t langmine .` succeeds

---

## M9: Vocabulary Depth

- [ ] **Vocab page navigable** — can navigate to vocab page and see word list
- [ ] **Vocab status filters** — tabs (All / Known / Learning / Unknown / Ignored) filter the word list
- [ ] **Vocab search** — search field filters words by text or reading
- [ ] **Word detail panel** — clicking a word row expands detail panel with status, reading, frequency, HSK level, and example sentences
- [ ] **Word highlighting on sentence cards** — known/learning/unknown/ignored words are colored differently
- [ ] **Popover status toggle** — clicking a word on a card opens popover with Mark Known / Mark Learning / Ignore / Unknown buttons
- [ ] **Mark known reclassifies** — marking a word as "known" triggers cascading reclassification of all sentences

---

## M10: Reading Mode

- [ ] **📖 Read tab visible** — Read tab appears in the tab bar when a video is selected
- [ ] **Full transcript display** — clicking Read shows all sentences (including deleted) as continuous text
- [ ] **Word highlighting in reading mode** — known/learning/unknown/ignored/proper-name words are color-coded
- [ ] **Word popover** — clicking a word in reading mode opens popover with frequency rank, HSK level, status, and action buttons
- [ ] **Popover close (Escape)** — pressing Escape closes the popover
- [ ] **Keyboard: ? shows legend** — pressing `?` toggles the fixed-bottom keyboard shortcuts bar
- [ ] **Keyboard: T toggles translation** — pressing `T` shows/hides translation lines in reading mode
- [ ] **Keyboard: R toggles annotations** — pressing `R` shows/hides character-level pinyin annotations
- [ ] **Sentence numbering** — each sentence shows its index number

---

## M11: Cloze Deletion Export

- [ ] **Cloze checkbox visible** — "🕳️ Cloze deletion cards" checkbox appears in Sidebar export section
- [ ] **Cloze checkbox toggle** — can check/uncheck the cloze checkbox
- [ ] **Cloze export to Anki** — exporting with cloze checked creates cloze deletion cards with `{{c1::word}}`
- [ ] **Basic export still works** — unchecking cloze exports standard cards as before
- [ ] **Cloze config in settings** — cloze note type, CSS, templates are configurable in Settings page

---

## M12: Image Search

- [ ] **Image search modal** — clicking "🔍 Search images" in word popover opens image picker modal
- [ ] **Image grid displays** — shows top-5 image results in a grid after clicking search
- [ ] **Image selection** — clicking an image selects it (visual highlight) and shows confirmation toast
- [ ] **Image persisted** — selected image now appears as a hint on the sentence card
- [ ] **Image in cloze export** — selected image appears as hint in cloze deletion card

---

## M13: Difficulty Preview

- [ ] **Preview button** — "🔍 Preview" button appears in sidebar next to the Mine button
- [ ] **Preview stats** — clicking Preview shows stats card (total sentences, i+1 estimated, known word %, avg unknowns per sentence)
- [ ] **Preview transcript** — read-only transcript with known/learning/unknown/proper-name word highlighting
- [ ] **Preview does not persist** — sentences shown in Preview are not saved to the database

---

## M14: Character Annotations + Dictionary

- [ ] **Annotate toggle** — "🎨 Annotate" toggle appears in reading mode toolbar
- [ ] **Annotation display** — enabling annotations shows pinyin above each character with Pleco tone colors:
  - 1st tone = red, 2nd = green, 3rd = blue, 4th = purple, 5th/neutral = gray
- [ ] **Annotation inline edit** — clicking an annotated character opens edit popover (reading, tone, definition)
- [ ] **Annotation edit save** — editing and saving persists via the annotation endpoint
- [ ] **Dictionary deep-dive link** — "📋 Show in dictionary" link in word popover navigates to VocabPage
- [ ] **VocabPage pre-populated** — clicking the link opens VocabPage with the word's detail panel auto-expanded

---

## M15: Multi-Language Support

- [ ] **Language selector appears** — top bar shows a `<select>` dropdown with available languages
- [ ] **Initial language is Chinese (中文)** — from default `source_language: "zh"`
- [ ] **Switching language reloads** — selecting a new language triggers config update and reloads videos
- [ ] **Data is isolated** — Chinese videos/sentences/vocab don't appear when browsing another language
- [ ] **Language persists** — after page reload, the selected language is remembered
- [ ] **Anki templates are per-language** — card CSS/HTML comes from `languages/<code>/anki/`, not from `config.yaml` inline templates

---

## M16: Event Timeline

> M16 is backend infrastructure — an append-only event log with 11 event types and `created_at`/`updated_at` timestamps.
> There is no user-facing timeline UI yet. Verify indirectly:

- [ ] **No errors on normal operations** — mining, curation, vocab updates, export all complete without errors or 500s
- [ ] **DB integrity** — `sqlite3 ~/.langmine/langmine.db "SELECT COUNT(*) FROM events"` returns a non-zero count after using the app

---

## M17: Ignore Word Status

- [ ] **🚫 Ignore button** — clicking a word in reading mode or curation opens popover with "🚫 Ignore" button
- [ ] **Word marked as ignored** — clicking Ignore changes the word's status badge to ignored (gray)
- [ ] **Stash reclassification** — ignoring a word triggers automatic reclassification of stashed sentences: any stash sentence that now has exactly 1 unknown word promotes to i+1
- [ ] **Vocab page shows Ignored filter** — "⬜ Ignored" filter tab shows ignored words
- [ ] **Vocab page status toggle** — can change an ignored word back to known/learning/unknown from the vocab detail panel

---

## M18: Proper Name Brackets

- [ ] **[Brackets] around proper names** — person and place names detected by jieba POS appear wrapped in `[square brackets]` in reading mode
- [ ] **Proper names excluded from i+1** — proper name words don't count as "unknown" for i+1 classification
- [ ] **Proper name popover** — clicking a bracketed word shows proper-name status and "❌ Not a proper name" button
- [ ] **Dismiss proper name** — clicking "Not a proper name" changes the word to learning status, removes brackets, and logs the dismissal

---

## Settings & Config

- [ ] **User-Agent override** — Network section in Settings accepts a custom User-Agent string
- [ ] **Rate-limit handling** — when YouTube blocks, error message shows actionable advice (wait/VPN/User-Agent/upload .srt)
- [ ] **Config fields visible** — Settings page shows: AnkiConnect URL, deck name, note type, cloze note type, card CSS, card templates, User-Agent

---

**Checklist version:** v1.3 — covers M0–M18, 2026-05-31
