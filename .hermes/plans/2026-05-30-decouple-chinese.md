# Decouple Mining Core from Chinese — Implementation Plan

> **For Hermes:** Use `subagent-driven-development` skill to implement this plan task-by-task.

**Goal:** Extract all Chinese-specific code into `languages/chinese/` so the core pipeline, web UI, and domain logic become language-agnostic. Spanish, Korean, and Russian can then be added as new language directories implementing the same port contracts.

**Architecture:** Monorepo with `languages/<lang>/` directory per language. Each provides a `LanguageProcessor` implementation + its `Dictionary` and `FrequencySource` adapters. Core (`domain/`, `pipeline.py`, `web/`) never imports from `languages/` — it uses the `LanguageProcessor` port, wired through a factory in `cli.py`/`app.py`.

**Tech Stack:** Python 3.11, jieba/pypinyin (Chinese only), pytest, Svelte 5, Playwright

**Status:** Planning — not yet implemented.

---

## Why We're Doing This

LangMine's sentence-mining pipeline is genuinely language-agnostic — segmentation, i+1 classification, audio clipping, transcript fetching — none of it cares about Chinese specifically. But the codebase is tangled:

1. **`domain/services/chinese.py`** lives in the domain layer, making Chinese look like "the" language rather than "one of" them.
2. **Chinese adapters** (CC-CEDICT, SUBTLEX-CH, HSK data) sit alongside language-agnostic adapters in `adapters/`, blurring the line.
3. **Model field names** (`pinyin`, `ruby_json`) assume Chinese phonetics — they work for Chinese but are semantically wrong for Spanish (where `reading` could be IPA) or Korean (where it could be romanization).
4. **Config** bakes in HSK proficiency levels — meaningless for non-Chinese languages.
5. **CLI and app.py** hardcode `ChineseLanguageService` with Chinese adapters — no way to switch languages without code changes.

The fix makes LangMine ready for Spanish, Korean, and Russian without touching the core pipeline, classifier, or web UI. Each language is a self-contained directory implementing well-defined ports.

---

## Agreed Design Decisions

| Decision | Choice |
|----------|--------|
| Repo structure | Monorepo — `languages/<lang>/` directory per language |
| Model field rename | `Sentence.pinyin` → `Sentence.reading`, `Sentence.ruby_json` → `Sentence.annotation_json` |
| Anki field rename | `sentence_pinyin` → `sentence_reading` (Anki note field) |
| Backward compatibility | None — clean break. This is a major refactor; migrate all at once |
| Language adapters location | `languages/<lang>/` — not in shared `adapters/` |
| Language-agnostic adapters stay | YouTube, yt-dlp, SQLite, AnkiConnect, GoogleTranslateAdapter, InlineTranscript, GoogleImageSearch stay in `adapters/` |
| HSK data | Moves to `languages/chinese/` |
| Config `hsk_bootstrap` | Removed from core Config. Each language extension handles its own proficiency framework |
| Factory pattern | `create_language_processor(config)` in a new `langmine/language_factory.py` module — returns the right `LanguageProcessor` for `config.source_language` |
| CI architecture check | Extended: domain must not import from `languages/`. Web must not import from `languages/`. Languages must not import from other languages or `web/` |

---

## Architecture Check (CI Enforcement)

The existing CI has three architecture grep rules. We'll add four more:

### Existing rules (keep)
```bash
# 1. domain/ never imports adapters
! grep -r "from.*adapters\|import.*adapters" src/langmine/domain/

# 2. domain/ never imports external I/O
! grep -r "sqlite3\|subprocess\|requests\|urllib" src/langmine/domain/

# 3. web/ never imports adapters (except app.py wiring)
WEB_ADAPTER_IMPORTS=$(grep -rl "from langmine.adapters" src/langmine/web/ || true)
if [ -n "$WEB_ADAPTER_IMPORTS" ]; then
  for f in $WEB_ADAPTER_IMPORTS; do
    case "$f" in */app.py) ;; *) echo "FAIL: $f imports adapters"; exit 1 ;; esac
  done
fi
```

### New rules (add)
```bash
# 4. domain/ never imports from languages/
! grep -r "from langmine.languages\|import langmine.languages" src/langmine/domain/

# 5. web/ never imports from languages/ (wired through ports + factory)
! grep -r "from langmine.languages\|import langmine.languages" src/langmine/web/

# 6. languages/ never imports from other languages/
#    (each language is self-contained — no cross-language coupling)
LANGS=$(ls -d src/langmine/languages/*/ 2>/dev/null || true)
for lang_dir in $LANGS; do
  lang_name=$(basename "$lang_dir")
  for other_dir in $LANGS; do
    other_name=$(basename "$other_dir")
    if [ "$lang_name" != "$other_name" ]; then
      if grep -r "from langmine.languages.$other_name\|import langmine.languages.$other_name" "$lang_dir" 2>/dev/null; then
        echo "FAIL: $lang_name imports from $other_name"; exit 1
      fi
    fi
  done
done

# 7. languages/ never imports from web/
! grep -r "from langmine.web\|import langmine.web" src/langmine/languages/
```

These go into `.github/workflows/ci.yml` under the `check` job, after the existing architecture steps. Also update `CONTRIBUTING.md` pre-commit checklist and the pre-merge architecture table.

---

## Implementation Tasks

### Phase 1: Model & Port Field Renames (foundation — everything builds on this)

#### Task 1.1: Rename `Sentence.pinyin` → `Sentence.reading`
**Objective:** Core model field name becomes language-agnostic.

**Files:**
- Modify: `src/langmine/domain/models.py` (`Sentence` dataclass)
- Modify: `src/langmine/domain/classifier.py` (`enrich()` method)
- Modify: `src/langmine/pipeline.py` (no change needed — uses `sentence.pinyin` indirectly via `enrich()`)
- Modify: `src/langmine/adapters/anki_connect.py` (Anki field `sentence_pinyin` → `sentence_reading`)
- Modify: `src/langmine/web/routes.py` (JSON serialization keys)
- Modify: `src/langmine/web/frontend/src/lib/SentenceCard.svelte`
- Modify: `src/langmine/web/frontend/src/lib/TranscriptView.svelte`
- Modify: `src/langmine/web/frontend/src/lib/VocabPage.svelte`
- Modify: `src/langmine/web/frontend/src/lib/PreviewPanel.svelte`
- Modify: `src/langmine/web/frontend/e2e/app.spec.js`
- Modify: `src/langmine/web/frontend/e2e/pages.js`
- Modify: All test files referencing `.pinyin`

**Step 1: Update Sentence model**
```python
# domain/models.py — change field name
# BEFORE:
pinyin: str = ""

# AFTER:
reading: str = ""   # Phonetic representation (pinyin for zh, IPA for es, etc.)
```

**Step 2: Update classifier**
```python
# domain/classifier.py — enrich()
# BEFORE:
sentence.pinyin = self._processor.get_reading(sentence.text)

# AFTER:
sentence.reading = self._processor.get_reading(sentence.text)
```

**Step 3: Update routes.py** (mass search-and-replace `pinyin` → `reading` in JSON response keys)
```python
# routes.py _sentence_to_dict()
# BEFORE:
"pinyin": sentence.pinyin,

# AFTER:
"reading": sentence.reading,
```
Also update `EDITABLE_FIELDS`:
```python
# BEFORE:
EDITABLE_FIELDS = {"pinyin", "translation_de", "text_segmented"}

# AFTER:
EDITABLE_FIELDS = {"reading", "translation_de", "text_segmented"}
```

**Step 4: Update Anki adapter** (Anki note field name)
```python
# adapters/anki_connect.py
# BEFORE:
"sentence_pinyin": s.pinyin or "",

# AFTER:
"sentence_reading": s.reading or "",
```
Also update the Anki model field definitions and card templates (CSS class `.pinyin` → `.reading`, template `{{sentence_pinyin}}` → `{{sentence_reading}}`).

**Step 5: Update config.py** card templates
```python
# config.py — card_back_template
# BEFORE:
'<div class="pinyin">{{sentence_pinyin}}</div>'

# AFTER:
'<div class="reading">{{sentence_reading}}</div>'
```
And CSS class `.pinyin` → `.reading` in both `card_css` and `cloze_card_css`.

**Step 6: Update all frontend components** (search-and-replace `.pinyin` → `.reading`, `sentence.pinyin` → `sentence.reading`, `word.pinyin` → `word.reading`)
- `SentenceCard.svelte`: field name in edit logic, CSS classes (`.pinyin-text` → `.reading-text`, `.pinyin-input` → `.reading-input`)
- `TranscriptView.svelte`: `sentence.pinyin` → `sentence.reading`, CSS `.sentence-pinyin` → `.sentence-reading`
- `VocabPage.svelte`: `word.pinyin` → `word.reading`, CSS classes, placeholder text
- `PreviewPanel.svelte`: `sentence.pinyin` → `sentence.reading`, CSS class

**Step 7: Update E2E tests**
- `e2e/pages.js`: `.pinyin-text` → `.reading-text`, `.pinyin-input` → `.reading-input`, `.sentence-pinyin` → `.sentence-reading`
- `e2e/app.spec.js`: test descriptions and locators

**Step 8: Update all test files** — search `pinyin` across `tests/` and replace references in assertions and fixtures.

**Step 9: Run tests** — `pytest tests/ -q --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py` and `npx playwright test`. All must pass.

**Step 10: Commit**
```bash
git add -A
git commit -m "refactor: rename Sentence.pinyin → Sentence.reading (language-agnostic)"
```

---

#### Task 1.2: Rename `Sentence.ruby_json` → `Sentence.annotation_json`
**Objective:** Character-level annotations become a generic field — `ruby` is CJK-specific.

**Files:**
- Modify: `src/langmine/domain/models.py` (`Sentence` dataclass)
- Modify: `src/langmine/domain/classifier.py` (`enrich()`)
- Modify: `src/langmine/domain/ports.py` (`LanguageProcessor.get_ruby()` → `get_annotation()`)
- Modify: `src/langmine/domain/services/chinese.py` (`get_ruby()` → `get_annotation()`)
- Modify: `src/langmine/web/routes.py` (field names, route path)
- Modify: `src/langmine/web/frontend/src/lib/TranscriptView.svelte`
- Modify: `src/langmine/web/frontend/e2e/app.spec.js`
- Modify: All test files referencing `ruby`

**Step 1: Update port method name**
```python
# domain/ports.py — LanguageProcessor
# BEFORE:
@abstractmethod
def get_ruby(self, text: str) -> str:
    """Return JSON string of [{char, pinyin, tone}] per character."""

# AFTER:
@abstractmethod
def get_annotation(self, text: str) -> str:
    """Return JSON string of character-level annotations.
    For CJK: [{char, pinyin, tone}]. Other languages may differ."""
```

**Step 2: Update ChineseLanguageService**
```python
# domain/services/chinese.py
# BEFORE:
def get_ruby(self, text: str) -> str:

# AFTER:
def get_annotation(self, text: str) -> str:
```

**Step 3: Update Sentence model**
```python
# domain/models.py
# BEFORE:
ruby_json: str = ""

# AFTER:
annotation_json: str = ""  # Character-level annotations (ruby for CJK, IPA, etc.)
```

**Step 4: Update classifier**
```python
# classifier.py — enrich()
# BEFORE:
sentence.ruby_json = self._processor.get_ruby(sentence.text)

# AFTER:
sentence.annotation_json = self._processor.get_annotation(sentence.text)
```

**Step 5: Update routes.py** — rename route and field names
```python
# routes.py
# Route: /api/sentences/<id>/ruby → /api/sentences/<id>/annotation
# Serialization: sentence.ruby_json → sentence.annotation_json
# Response key: "ruby" → "annotation"
```

**Step 6: Update frontend**
- `TranscriptView.svelte`: `sentence.ruby` → `sentence.annotation`, `showRuby` → `showAnnotation`, "🎨 Ruby" button → "🎨 Annotate", `R` shortcut stays, CSS classes `.ruby-char` → `.annotated-char`

**Step 7: Update E2E tests and all test files**

**Step 8: Run full test suite → pass**

**Step 9: Commit**
```bash
git commit -m "refactor: rename ruby_json → annotation_json (language-agnostic annotations)"
```

---

### Phase 2: Create `languages/` Directory & Move Chinese

#### Task 2.1: Create directory structure
```bash
mkdir -p src/langmine/languages/chinese/data
touch src/langmine/languages/__init__.py
touch src/langmine/languages/chinese/__init__.py
```

#### Task 2.2: Move Chinese language service
**Move:** `src/langmine/domain/services/chinese.py` → `src/langmine/languages/chinese/service.py`

Update imports inside the file — it now lives at `langmine.languages.chinese.service`, not `langmine.domain.services.chinese`.

#### Task 2.3: Move Chinese adapters
Move language-specific adapters from `adapters/` to `languages/chinese/`:

```bash
git mv src/langmine/adapters/cc_cedict.py    src/langmine/languages/chinese/dictionary.py
git mv src/langmine/adapters/subtlex_ch.py   src/langmine/languages/chinese/frequency.py
git mv src/langmine/adapters/jieba_frequency.py src/langmine/languages/chinese/jieba_frequency.py
git mv src/langmine/adapters/hsk.py          src/langmine/languages/chinese/hsk.py
git mv src/langmine/hsk_data.py              src/langmine/languages/chinese/hsk_data.py
```

Update all imports inside these files — they now live at `langmine.languages.chinese.*`, not `langmine.adapters.*`.

#### Task 2.4: Move SUBTLEX-CH-WF data file
```bash
git mv data/SUBTLEX-CH-WF  src/langmine/languages/chinese/data/SUBTLEX-CH-WF
```

Update `frequency.py` to reference the new path:
```python
# languages/chinese/frequency.py
# BEFORE:
_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "SUBTLEX-CH-WF"

# AFTER:
_DATA_PATH = Path(__file__).parent / "data" / "SUBTLEX-CH-WF"
```

#### Task 2.5: Update `adapters/__init__.py`
Remove exports for moved adapters. Export only language-agnostic adapters:
```python
from langmine.adapters.youtube_transcript import YouTubeTranscriptAdapter
from langmine.adapters.ytdlp_audio import YtdlpAudioAdapter
from langmine.adapters.sqlite_persistence import SQLitePersistence
from langmine.adapters.google_translate import GoogleTranslateAdapter
from langmine.adapters.anki_connect import AnkiConnectAdapter
from langmine.adapters.inline_transcript import InlineTranscriptSource
from langmine.adapters.google_image_search import GoogleImageSearch
# CcCedictAdapter, SubtlexChAdapter, JiebaFrequencyAdapter moved to languages/chinese/
```

#### Task 2.6: Create `languages/chinese/__init__.py` — public API
```python
"""Chinese language extension for LangMine.

Provides:
  - ChineseLanguageService (LanguageProcessor implementation)
  - CcCedictAdapter (Dictionary implementation)
  - SubtlexChAdapter (FrequencySource implementation)
  - get_hsk_level (HSK proficiency utility)
"""

from langmine.languages.chinese.service import ChineseLanguageService
from langmine.languages.chinese.dictionary import CcCedictAdapter
from langmine.languages.chinese.frequency import SubtlexChAdapter
from langmine.languages.chinese.hsk_data import get_hsk_level

__all__ = [
    "ChineseLanguageService",
    "CcCedictAdapter",
    "SubtlexChAdapter",
    "get_hsk_level",
]
```

#### Task 2.7: Update all imports across the codebase
Search-and-replace across ALL files:
```
from langmine.adapters.cc_cedict    → from langmine.languages.chinese
from langmine.adapters.subtlex_ch   → from langmine.languages.chinese
from langmine.adapters.hsk          → from langmine.languages.chinese
from langmine.hsk_data              → from langmine.languages.chinese.hsk_data
from langmine.domain.services.chinese → from langmine.languages.chinese
from langmine.adapters.jieba_frequency → from langmine.languages.chinese
```

Files affected:
- `cli.py` (2 locations: `_cmd_mine`, `_cmd_serve`)
- `web/app.py`
- `tests/test_chinese_service.py` (or rename to `tests/languages/test_chinese_service.py`)
- `tests/test_process_video.py`
- `tests/adapters/test_subtlex_ch.py` → `tests/languages/test_subtlex_ch.py`
- `e2e/test_server.py`

#### Task 2.8: Run full test suite → must pass

#### Task 2.9: Commit
```bash
git add -A
git commit -m "refactor: extract Chinese language code to languages/chinese/"
```

---

### Phase 3: Language Factory + Config Cleanup

#### Task 3.1: Create `langmine/language_factory.py`
```python
"""Language processor factory — creates the right LanguageProcessor per config."""

from langmine.domain.ports import LanguageProcessor
from langmine.config import Config


def create_language_processor(config: Config) -> LanguageProcessor:
    """Create a LanguageProcessor for the configured source language.

    Each language extension provides its own service + adapters.
    This factory is the ONLY place that imports from languages/.
    """
    from langmine.adapters.google_translate import GoogleTranslateAdapter

    translator = GoogleTranslateAdapter()

    match config.source_language:
        case "zh":
            from langmine.languages.chinese import (
                ChineseLanguageService,
                CcCedictAdapter,
                SubtlexChAdapter,
            )
            return ChineseLanguageService(
                CcCedictAdapter(),
                translator,
                SubtlexChAdapter(),
            )

        case "es":
            # Placeholder — will be implemented in a future milestone
            raise NotImplementedError(
                "Spanish language extension not yet implemented. "
                "Create languages/spanish/ with SpanishLanguageService."
            )

        case "ko":
            raise NotImplementedError("Korean language extension not yet implemented.")

        case "ru":
            raise NotImplementedError("Russian language extension not yet implemented.")

        case _:
            raise ValueError(
                f"Unsupported source language: {config.source_language}. "
                "Add a language extension under languages/<lang>/."
            )
```

#### Task 3.2: Update `cli.py` to use factory
Replace hardcoded Chinese wiring in `_cmd_mine` and `_cmd_serve`:
```python
# BEFORE:
from langmine.languages.chinese import ChineseLanguageService
from langmine.adapters import CcCedictAdapter, SubtlexChAdapter
processor = ChineseLanguageService(CcCedictAdapter(), GoogleTranslateAdapter(), SubtlexChAdapter())

# AFTER:
from langmine.language_factory import create_language_processor
processor = create_language_processor(config)
```

#### Task 3.3: Update `web/app.py` to accept `language_processor` injection
`app.py` already accepts `language_processor: LanguageProcessor | None`. The `_cmd_serve` function creates it. Replace:
```python
# BEFORE in _cmd_serve():
from langmine.languages.chinese import ChineseLanguageService
from langmine.adapters import CcCedictAdapter, SubtlexChAdapter
processor = ChineseLanguageService(CcCedictAdapter(), GoogleTranslateAdapter(), SubtlexChAdapter())

# AFTER:
from langmine.language_factory import create_language_processor
processor = create_language_processor(config)
```

#### Task 3.4: Remove `hsk_bootstrap` from core Config
```python
# config.py — remove from Config dataclass, _config_to_dict(), _dict_to_config(), routes.py ALLOWED set, SettingsPage.svelte
```

`hsk_bootstrap` becomes Chinese-extension territory. If needed, Chinese extension can read it from a `languages.chinese.config` module or a dedicated config section:
```yaml
# config.yaml
languages:
  source: zh
  target: de
  chinese:
    hsk_bootstrap: 3
```
But that's a Chinese-extension concern — not core.

#### Task 3.5: Update `SettingsPage.svelte`
Remove HSK bootstrap input. The "Vocab" section in settings no longer needs it.

#### Task 3.6: Update `routes.py` `get_config()` and `update_config()` ALLOWED set
Remove `hsk_bootstrap` from the exposed config keys.

#### Task 3.7: Update tests
- Update `test_config.py` to remove `hsk_bootstrap` assertions
- Update `test_web_api.py` to remove HSK config endpoints
- E2E tests: remove HSK settings assertions

#### Task 3.8: Run full test suite → pass

#### Task 3.9: Commit
```bash
git commit -m "refactor: add language factory, remove hsk_bootstrap from core config"
```

---

### Phase 4: CI Architecture Checks

#### Task 4.1: Add language-decoupling checks to CI
Modify `.github/workflows/ci.yml` — add 4 new steps after the existing architecture checks:

```yaml
- name: "Architecture: domain never imports from languages/"
  run: |
    echo "=== Cardinal rule: domain → languages must be empty ==="
    ! grep -r "from langmine.languages\|import langmine.languages" src/langmine/domain/

- name: "Architecture: web never imports from languages/"
  run: |
    echo "=== Web must not import languages (use port + factory) ==="
    ! grep -r "from langmine.languages\|import langmine.languages" src/langmine/web/

- name: "Architecture: languages never cross-import"
  run: |
    echo "=== Each language is self-contained ==="
    LANGS=$(ls -d src/langmine/languages/*/ 2>/dev/null || true)
    for lang_dir in $LANGS; do
      lang_name=$(basename "$lang_dir")
      for other_dir in $LANGS; do
        other_name=$(basename "$other_dir")
        if [ "$lang_name" != "$other_name" ]; then
          if grep -r "from langmine.languages.$other_name\|import langmine.languages.$other_name" "$lang_dir" 2>/dev/null; then
            echo "FAIL: $lang_name imports from $other_name"
            exit 1
          fi
        fi
      done
    done

- name: "Architecture: languages never import from web/"
  run: |
    echo "=== Languages must not import web layer ==="
    ! grep -r "from langmine.web\|import langmine.web" src/langmine/languages/
```

#### Task 4.2: Update CONTRIBUTING.md
Update the architecture section and pre-commit checklist to include the new rules. Add new rows to the pre-merge checklist table.

#### Task 4.3: Verify CI catches violations
Temporarily add a forbidden import, push to a test branch, verify CI fails, revert, push again, verify CI passes.

#### Task 4.4: Commit
```bash
git commit -m "ci: add language-decoupling architecture checks"
```

---

### Phase 5: Test Reorganization

#### Task 5.1: Move Chinese-specific tests
```bash
mkdir -p tests/languages/chinese
git mv tests/test_chinese_service.py      tests/languages/chinese/test_service.py
git mv tests/adapters/test_subtlex_ch.py  tests/languages/chinese/test_frequency.py
```

Update imports in moved tests to reference `langmine.languages.chinese.*`.

#### Task 5.2: Update test conftest and fixtures
Ensure `tests/conftest.py` has no Chinese-specific imports. The `FakeLanguageProcessor` class in tests already implements `LanguageProcessor` port — verify it still works after renames.

#### Task 5.3: Run full test suite → pass

#### Task 5.4: Commit
```bash
git commit -m "test: move Chinese-specific tests to tests/languages/chinese/"
```

---

### Phase 6: Frontend Cleanup — Remove Chinese Assumptions

#### Task 6.1: Audit all frontend component references
The field renames (Phase 1) handled model field names. Now handle:

- `VocabPage.svelte`: search placeholder "Search by word or pinyin..." → "Search by word or reading..."
- `SentenceCard.svelte`: word popover showing `hsk_level` — make this optional (only render if present in JSON)
- `TranscriptView.svelte`: ruby toggle button — keep but rename to "Annotate", keep `R` shortcut
- `SettingsPage.svelte`: remove HSK bootstrap field

**Key principle:** The frontend should render whatever the API returns. If `hsk_level` is present on a word, show it. If not, don't. No Chinese-specific assumptions.

#### Task 6.2: Rebuild frontend + E2E pass
```bash
cd src/langmine/web/frontend && npm run build && npx playwright test && cd -
```

#### Task 6.3: Commit
```bash
git commit -m "refactor: remove Chinese assumptions from frontend"
```

---

### Phase 7: Documentation

#### Task 7.1: Update ARCHITECTURE.md
- Add `languages/` directory to the directory tree
- Add language extension rules to the dependency graph
- Update port/adapter table: Chinese adapters move to `languages/chinese/`

#### Task 7.2: Update CONTRIBUTING.md
- Update directory tree
- Add section: "Adding a new language extension" — what files to create, what interfaces to implement
- Update port/adapter table
- Update pre-commit and pre-merge checklists with new arch rules

#### Task 7.3: Update README.md
- Update status / milestone info
- Mention multi-language support
- Update test counts

#### Task 7.4: Update HANDOFF.md
- Update current milestone
- Note language extraction

#### Task 7.5: Commit
```bash
git commit -m "docs: update docs for language decoupling"
```

---

## Final Directory Structure (after all phases)

```
src/langmine/
├── domain/
│   ├── __init__.py
│   ├── ports.py           # LanguageProcessor, Dictionary, FrequencySource, etc.
│   ├── models.py           # Sentence.reading, Sentence.annotation_json
│   ├── classifier.py       # Language-agnostic i+1 engine
│   └── services/
│       └── __init__.py     # (empty — services moved to languages/)
│
├── adapters/               # LANGUAGE-AGNOSTIC adapters only
│   ├── __init__.py
│   ├── youtube_transcript.py
│   ├── ytdlp_audio.py
│   ├── sqlite_persistence.py
│   ├── google_translate.py
│   ├── google_image_search.py
│   ├── anki_connect.py
│   └── inline_transcript.py
│
├── languages/              # LANGUAGE-SPECIFIC extensions
│   ├── __init__.py
│   └── chinese/
│       ├── __init__.py        # Public API: ChineseLanguageService, CcCedictAdapter, SubtlexChAdapter
│       ├── service.py         # ChineseLanguageService (LanguageProcessor)
│       ├── dictionary.py      # CcCedictAdapter (Dictionary port)
│       ├── frequency.py       # SubtlexChAdapter (FrequencySource port)
│       ├── jieba_frequency.py # JiebaFrequencyAdapter (fallback FrequencySource)
│       ├── hsk.py             # get_hsk_level re-export
│       ├── hsk_data.py        # HSK vocabulary data
│       └── data/
│           └── SUBTLEX-CH-WF  # 2.5 MB frequency corpus
│
├── language_factory.py    # create_language_processor(config) — ONLY place that imports from languages/
├── pipeline.py            # Unchanged — takes LanguageProcessor port
├── cli.py                 # Uses factory, not hardcoded Chinese
├── web/                   # Unchanged — serves whatever language processor is injected
├── config.py              # No hsk_bootstrap, no Chinese defaults
├── transcript.py          # Unchanged
├── transcript_parser.py   # Unchanged
├── audio.py               # Unchanged
├── db.py                  # Unchanged
└── processors.py          # Unchanged

tests/
├── conftest.py
├── test_classifier.py
├── test_web_api.py
├── ...
├── adapters/
│   └── test_anki_connect.py
└── languages/
    └── chinese/
        ├── test_service.py
        └── test_frequency.py
```

---

## Language Extension Contract

To add a new language (e.g., Spanish), create `languages/spanish/` with:

```
languages/spanish/
├── __init__.py        # Exports SpanishLanguageService, SpanishDictAdapter, SubtlexEsAdapter
├── service.py         # SpanishLanguageService(LanguageProcessor)
│                      #   - segment() → spaCy/stanza Spanish tokenizer
│                      #   - get_reading() → IPA transcription
│                      #   - is_non_word() → Spanish particles (de, que, y, el, la, ...)
│                      #   - lookup_word() → delegates to Dictionary port
│                      #   - translate_sentence() → delegates to Translator port
│                      #   - get_frequency() → delegates to FrequencySource port
│                      #   - find_known_synonyms() → Spanish synonym detection
│                      #   - get_annotation() → returns [] (or syllable stress if desired)
├── dictionary.py      # SpanishDictAdapter (Dictionary port)
├── frequency.py       # SubtlexEsAdapter (FrequencySource port)
└── data/
    └── SUBTLEX-ES     # Spanish subtitle frequency corpus
```

Then add a `case "es"` branch in `language_factory.py`. That's it — the pipeline, classifier, web UI, audio processing all work without changes.

---

## Verification Checklist

After all phases:

```bash
# 1. Architecture checks (same as CI)
! grep -r "from.*adapters\|import.*adapters" src/langmine/domain/
! grep -r "sqlite3\|subprocess\|requests\|urllib" src/langmine/domain/
! grep -r "from langmine.languages\|import langmine.languages" src/langmine/domain/
! grep -r "from langmine.languages\|import langmine.languages" src/langmine/web/
# Cross-language import check (manual or via CI script above)

# 2. All tests pass
pytest tests/ -q --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py

# 3. E2E tests pass
cd src/langmine/web/frontend && npx playwright test && cd -

# 4. Frontend builds
cd src/langmine/web/frontend && npm run build && cd -

# 5. Server starts
langmine serve --port 8080 &
# → visit http://localhost:8080
# → mine a Chinese video
# → verify curation, reading view, ruby annotations, vocab page all work
```
