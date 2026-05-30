# LangMine Acceptance Test Checklist — M0–M15

> Manual QA checklist. Run through these in order after a fresh deploy.
> Each item is one observable pass/fail check.

---

## M0–M2: Mine, Classify, Pipeline

- [ ] **CLI mine succeeds** — `langmine mine "<youtube-url>"` downloads transcript, produces sentences with audio clips
- [ ] **Pipeline produces output** — `data/` directory fills with `.mp3` audio clips per sentence
- [ ] **i+1 classifier runs** — sentences are classified (known=1-unknown, learnable=i+1, too-hard=i+2+)
- [ ] **HSK bootstrap works** — words in HSK 1–3 are treated as "known" by default

---

## M3: Curate in Browser (Web UI)

- [ ] **App loads** — `langmine serve` → `http://localhost:8080` shows sidebar + empty state
- [ ] **Sidebar shows video list** — mined videos appear in the left sidebar
- [ ] **Click video loads sentences** — selecting a video populates the card list
- [ ] **Filter tabs work** — All / Kept / Deleted / Stash tabs show correct sentence subsets
- [ ] **Keep button** — clicking Keep moves sentence to Kept filter, updates status badge
- [ ] **Delete button** — shows confirmation prompt, then moves sentence to Deleted
- [ ] **Empty state** — each tab shows a message when no sentences match

---

## M4: Translate & Understand (NLP)

- [ ] **Chinese segmentation** — sentences show segmented words (spaces between tokens)
- [ ] **Pinyin displayed** — each sentence card shows pinyin below the Chinese text
- [ ] **Translation displayed** — each sentence card shows German (target language) translation
- [ ] **Frequency badge** — unknown words show frequency rank and tier icon (🔥/⭐/💎)
- [ ] **HSK level badge** — known words show HSK level when available

---

## M5: Export to Anki

- [ ] **Export All Kept** — `langmine export --all-kept` pushes cards to Anki via AnkiConnect
- [ ] **Export by video** — `langmine export --video-id <id>` exports single-video cards
- [ ] **Cards appear in Anki** — deck "Chinese::Sentence Mining" receives cards with audio + translation
- [ ] **Force-update model** — `--force-update-model` pushes template changes from `config.yaml`
- [ ] **Web UI export button** — "📦 Export to Anki" button in sidebar triggers export

---

## M6: Stash & Screenshots

- [ ] **Stash tab** — shows i+2+ sentences in descending score order
- [ ] **Stash empty state** — shows message when no stashed sentences
- [ ] **Stash sentences are kept** — clicking Keep on a stash sentence moves it to Kept
- [ ] **Screenshots captured** — sentence cards show a frame from the video at the sentence timestamp
- [ ] **Screenshot in Anki** — exported cards include the screenshot on the back

---

## M7: Polish & Edit

- [ ] **Inline pinyin edit** — click pinyin on a card → input field → edit → save persists
- [ ] **Inline translation edit** — click translation → edit → save persists
- [ ] **Cancel edit (Escape)** — pressing Escape during inline edit returns to display mode
- [ ] **Settings page** — gear icon or nav link opens Settings page with config form
- [ ] **Settings save** — changing a value and clicking Save updates `config.yaml`
- [ ] **Dark/light theme toggle** — theme switch toggles between dark and light mode
- [ ] **Theme persists** — refreshing the page keeps the selected theme
- [ ] **Validation on empty input** — mine form shows error when submitted with empty URL

---

## M8: Docker Deployment

- [ ] **docker compose up** — `docker compose up` starts the app on port 8080
- [ ] **AnkiConnect reachable** — export to Anki works from inside Docker (`host.docker.internal`)
- [ ] **docker run** — single `docker run` command starts the app
- [ ] **Build from source** — `docker build -t langmine .` succeeds

---

## M9: Vocabulary Depth

- [ ] **Vocab page navigable** — can navigate to vocab page and see word list
- [ ] **Vocab status filters** — tabs (All / Known / Learning / Unknown) filter the word list
- [ ] **Vocab search** — search field filters words by text
- [ ] **Word detail panel** — clicking a word row expands detail panel with status and sentences
- [ ] **Word highlighting on sentence cards** — known/learning/unknown words are colored differently
- [ ] **Popover status toggle** — clicking a word on a card opens popover with Mark Known/Learning/Unknown
- [ ] **Mark known reclassifies** — marking a word as "known" triggers cascading reclassification of all sentences
- [ ] **Vocab API returns paginated words** — `GET /api/vocab` with query parameters
- [ ] **CORS headers** — API responses include CORS-friendly headers

---

## M10: Reading Mode

- [ ] **📖 Read tab visible** — Read tab appears in the tab bar when a video is selected
- [ ] **Full transcript display** — clicking Read shows all sentences (including deleted) as continuous text
- [ ] **Word highlighting in reading mode** — known/learning/unknown words are color-coded
- [ ] **Word popover** — clicking a word in reading mode opens popover with HSK level, frequency rank, status
- [ ] **Popover close (Escape)** — pressing Escape closes the popover
- [ ] **Keyboard: ? shows legend** — pressing `?` toggles the fixed-bottom keyboard shortcuts bar
- [ ] **Keyboard: T toggles translation** — pressing `T` shows/hides translation lines in reading mode
- [ ] **Sentence numbering** — each sentence shows its index number

---

## M11: Cloze Deletion Export

- [ ] **Cloze checkbox visible** — "🕳️ Cloze deletion cards" checkbox appears in Sidebar export section
- [ ] **Cloze checkbox toggle** — can check/uncheck the cloze checkbox
- [ ] **Cloze export to API** — exporting with cloze checked sends `card_type=cloze` to API
- [ ] **Basic export still works** — unchecking cloze exports standard cards as before
- [ ] **Cloze config in settings** — cloze note type, CSS, templates editable in Settings page

---

## M12: Image Search

- [ ] **Image search modal** — clicking "🔍 Search images" in word popover opens image picker modal
- [ ] **Image grid displays** — shows top-5 image results in a grid
- [ ] **Image selection** — clicking an image selects it (visual highlight)
- [ ] **Image persisted** — selected image stored and shown on sentence card
- [ ] **Image in cloze export** — selected image appears as hint in cloze card
- [ ] **Image search API** — `GET /api/images/search?q=...` returns valid image URLs

---

## M13: Difficulty Preview

- [ ] **Preview button** — "🔍 Preview" button appears in sidebar next to URL input
- [ ] **Preview stats** — clicking Preview shows stats card (total sentences, i+1 estimated, known word %, etc.)
- [ ] **Preview transcript** — read-only transcript with known/learning/unknown word highlighting
- [ ] **Preview does not persist** — sentences shown in Preview are not saved to the database
- [ ] **Preview API endpoint** — `POST /api/videos/preview` returns stats + annotated sentences

---

## M14: Ruby Annotations + Dictionary

- [ ] **Ruby toggle** — "🎨 Ruby" toggle appears in reading mode toolbar
- [ ] **Ruby display** — enabling ruby shows pinyin above each character with Pleco tone colors:
  - 1st tone = red, 2nd = green, 3rd = blue, 4th = purple, 5th/neutral = gray
- [ ] **Ruby inline edit** — clicking a ruby character opens edit popover (pinyin, tone, definition)
- [ ] **Ruby edit save** — `PATCH /api/sentences/:id/ruby` persists corrections
- [ ] **Dictionary deep-dive link** — "📋 Show in dictionary" link in word popover navigates to VocabPage
- [ ] **VocabPage pre-populated** — clicking the link opens VocabPage with `?search=<word>` pre-filled

---

## Settings & Config

- [ ] **User-Agent override** — Network section in Settings accepts a custom User-Agent string
- [ ] **Rate-limit handling** — when YouTube blocks, error message shows actionable advice (wait/VPN/User-Agent/upload .srt)
- [ ] **Config surface clean** — Settings page shows `anki_connect_url` but NOT `deck_name`/`note_type`

---

## M15: Multi-Language Support

- [ ] **Language selector appears** — top bar shows a `<select>` dropdown with available languages
- [ ] **Initial language is Chinese (中文)** — from default `source_language: "zh"`
- [ ] **`GET /api/languages`** returns `{"languages": [{"code": "zh", "name": "中文"}]}`
- [ ] **Switching language calls config PATCH** — selecting a new language triggers `PUT /api/config` with `source_language`
- [ ] **Data is isolated** — Chinese videos/sentences/vocab don't appear when browsing another language
- [ ] **Language persists in config** — after page reload, the selected language is remembered
- [ ] **Anki templates are per-language** — card CSS/HTML comes from `languages/chinese/anki/`, not config.yaml

---

**Checklist version:** v1.2 — covers M0–M15, 2026-05-31
