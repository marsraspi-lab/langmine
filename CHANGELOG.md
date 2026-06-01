# Changelog

All notable changes to LangMine.

## [1.6.0] — 2026-06-01

### Added

- **M24: Sentence Joining** — `POST /api/sentences/<id>/merge-with-previous` endpoint. Merges sentence B into the previous sentence A: concatenates `text`, `text_segmented`, `reading`, `translation_de`; spans timing from A's `start_ms` to B's `end_ms`; soft-deletes B; reclassifies the merged sentence.
- **Frontend merge button** — ⬆️ Merge button on non-first sentence cards in curation view. Calls `mergeWithPrevious()` API function, reloads sentence list on success. Toast feedback on merge/failure.
- **`_get_sentence_or_404()` helper** in `routes.py`.

### Changed

- **E2E**: 51 tests (up from 49). New merge E2E test verifies button visibility, first-sentence guard, merge POST.

---

## [1.5.0] — 2026-06-01

### Added

- **M23: Word Splitting** — click `text_segmented` inline to edit word boundaries. Type spaces between words; saved as `word1 / word2 / word3` format. `_reclassify_from_segmented()` reclassifies the sentence after editing.
- **M22: Add Sentences** — `reclassify_all()` domain method + `POST /api/videos/<id>/reclassify?offset=N&limit=M` endpoint. "🔄 Reclassify & sort" and "+ Add more sentences" buttons in curation view with pagination.
- **M21: HSK Bootstrap** — `_bootstrap_hsk()` pre-marks HSK words as `known` from language extension proficiency data.
- **M20: Manual Proper Names** — `PATCH /api/vocab/<word>` now accepts `{status: "proper-name"}` and `{proper_name: true/false}`. "👤 Mark as proper name" and "❌ Not a proper name" buttons in word popovers. Guard in `_words_array` prevents re-detection of dismissed proper names.
- **M19: Client-Side Curation** — `knownWords`/`learningWords`/`ignoredWords` Svelte hashmaps. `curatedSentences` derived store computes `computedStatus` client-side. All sentences visible. Instant word highlighting — no server roundtrip for word status changes.

### Changed

- **E2E**: 49 tests (up from 42). New tests for word splitting, add sentences pagination, proper-name marking/dismissal.
- **Pytest**: 234 tests (up from 206). New tests for proper-name guard, merge endpoint, reclassification.

---

## [1.2.0] — 2026-05-31

### Added

- **Multi-language data isolation** — `language_code` column on `videos`, `sentences`, and `vocab` tables. Data from different languages is partitioned; switching languages filters all views without purging data.
- **`GET /api/languages`** endpoint — returns `[{code, name}]` for all registered language extensions. Currently returns `[{code: "zh", name: "中文"}]`.
- **Language selector in top bar** — `<select>` dropdown in Svelte UI. Changing the language calls `PUT /api/config` with `source_language` and reloads all data scoped to the new language.
- **Language manifest** (`languages/<lang>/__init__.py`) — each language extension now declares `MANIFEST` with `name`, `deck_name`, `note_type`, and `cloze_note_type`. The Anki export route reads these instead of config.
- **Anki templates as files** — card templates moved from `config.yaml` / `Config` class to `languages/chinese/anki/{basic,cloze}/{front.html,back.html,css.css}`. Loaded by `get_anki_templates()` in the language factory. Adding a new language means creating its own template files.
- **`get_language_manifest()`** and **`get_anki_templates()`** functions in `language_factory.py` — dispatch to the active language extension.
- **Tests** — `tests/test_multi_language.py` (5 tests: schema + isolation), `/api/languages` tests (2 tests). All FakePersistence classes in test files accept `language_code` parameters.

### Changed

- **`/api/config`** — `deck_name` and `note_type` removed from the response (now in language manifest). Template fields (`card_css`, `card_front_template`, `card_back_template`, `cloze_*`) removed from the PUT ALLOWED set — they live in language extension files.
- **`/api/export/anki`** — now sources `deck_name`, `note_type`, and card templates from the language manifest + template files instead of `config.yaml`.
- **SettingsPage** (Svelte) — removed Deck Name and Note Type input fields (moved to language extension).
- **E2E tests** — `deck_name` assertions replaced with `anki_connect_url`; `SettingsPage.saveDeckName()` now exercises the Anki URL field.

### Removed

- No data removed. Existing `~/.langmine/langmine.db` with old schema will **not** get the `language_code` column through `CREATE TABLE IF NOT EXISTS` — delete the DB file to recreate with the new schema, or run a manual `ALTER TABLE` migration. (No production users yet.)

---

## [1.1.0] — 2026-05-30

### Added

- **Language factory** (`src/langmine/language_factory.py`) — `create_language_processor(Config)` dispatches to the right `LanguageProcessor` for `config.source_language`. `get_proficiency_level(word)` delegates to the configured language's proficiency framework.
- **`languages/` directory** — each language is a self-contained package under `languages/<lang>/`.
  - `languages/chinese/` — `ChineseLanguageService`, `CcCedictAdapter`, `SubtlexChAdapter`, `JiebaFrequencyAdapter`, `get_hsk_level`.
- **Architecture CI rules** — domain must not import from `languages/`; web must not import from `languages/`; languages must not import from other languages or `web/`.

### Changed

- **Model field renames** (backward-incompatible):
  - `Sentence.pinyin` → `Sentence.reading`
  - `Sentence.ruby_json` → `Sentence.annotation_json`
  - `VocabWord.pinyin` → `VocabWord.reading`
- **Port method rename** — `LanguageProcessor.get_ruby()` → `LanguageProcessor.get_annotation()`.
- **API route rename** — `/api/sentences/<id>/ruby` → `/api/sentences/<id>/annotation`.
- **Adapter imports** — Chinese-specific adapters (`CcCedictAdapter`, `SubtlexChAdapter`, `JiebaFrequencyAdapter`, `HSK`) moved from `langmine.adapters` to `langmine.languages.chinese`. Language-agnostic adapters (`YouTubeTranscript`, `YtdlpAudio`, `SQLitePersistence`, `AnkiConnect`, `GoogleTranslate`, `GoogleImageSearch`) stay in `adapters/`.
- **Config** — `hsk_bootstrap` field removed from `Config`. HSK proficiency is now an internal detail of the Chinese language extension.
- **Frontend** — all "pinyin" references in `VocabPage`, `SentenceCard`, `TranscriptView` changed to "reading".
- **Tests** — Chinese-specific tests moved to `tests/languages/chinese/`. Imports updated throughout.
- **Documentation** — `ARCHITECTURE.md`, `CONTRIBUTING.md`, `HANDOFF.md`, `README.md` updated with new structure and language-isolation rules.

### Removed

- `src/langmine/domain/services/chinese.py` — extracted into `languages/chinese/`.
- `src/langmine/adapters/cc_cedict.py`, `subtlex_ch.py`, `hsk_data.py`, `jieba_frequency.py` — moved to `languages/chinese/`.
- `src/langmine/config.py` `hsk_bootstrap` field.

---

## [1.0.0] — 2026-05-30

### Added

- **Version infrastructure**:
  - `pyproject.toml` bumped to `1.0.0` (single source of truth).
  - `langmine --version` CLI flag via `importlib.metadata.version`.
  - `GET /api/version` endpoint returns `{version, name}`.
  - Version footer in SettingsPage (Svelte).
  - `ARG VERSION` and `org.opencontainers.image.version` label in Dockerfile.
- **Milestones M0–M14 complete** — sentence mining, i+1 classification, Anki export, cloze deletion, image search, difficulty preview, ruby annotations, vocabulary browser, reading mode.

### Removed

- Stale HSK Bootstrap UI from SettingsPage.

---

## Pre-1.0.0

Milestones M0 through M14 shipped incrementally. Highlights:
- **M0–M4**: Core pipeline — transcript fetching, audio download/clip, sentence segmentation, i+1 classification.
- **M5–M7**: Web UI — Svelte SPA with Flask API, video sidebar, card list, curation actions.
- **M8**: AnkiConnect export — basic cards with audio and screenshots.
- **M9**: Vocabulary page — word list with status management (known/learning).
- **M10**: Reading mode — transcript view with word popovers and keyboard shortcuts.
- **M11**: Cloze deletion export — alternate card type for recall practice.
- **M12**: Image search — Google CSE adapter, image picker for cloze hints.
- **M13**: Difficulty preview — pre-mining stats without full processing.
- **M14**: Ruby annotations + dictionary deep-dive — CC-CEDICT details panel.
