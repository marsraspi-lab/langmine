# Language-Specific Settings Design

**Date:** 2026-06-04
**Status:** Draft

## Context

The current `Config` dataclass and `config.yaml` are flat — all 24 fields are global. The `hsk_bootstrap_level` field lives under `mining:` in the YAML and appears in the Settings UI unconditionally, even though it's only meaningful for Chinese. When a second language (e.g. Spanish) is added, there is no mechanism for language-specific proficiency frameworks, Anki deck names, or mining defaults.

Additionally, the current `<select>` binding for `hsk_bootstrap_level` in `SettingsPage.svelte` is buggy — it uses Svelte one-way `value={}` on the `<select>` element without per-option `selected` attributes, so saved values are not preselected when the page loads.

## Goals

1. Config stores per-language settings in a `language_settings` dict keyed by language code
2. Each language package defines its own settings schema (fields, types, defaults, options) and **reads/writes its own settings** — pipeline and routes never know about specific setting keys
3. The Settings UI renders language-specific controls dynamically from the schema, only for the active language
4. Remove `hsk_bootstrap_level` entirely — no deprecation, no migration
5. Fix the existing preselect and save bugs

## Non-Goals

- No per-language config files (settings stay in a single `config.yaml`)
- No UI for editing settings of non-active languages
- The `source_language` / `target_language` fields remain global

---

## Design

### 1. Config Data Model

Add `language_settings` and remove `hsk_bootstrap_level`:

```python
@dataclass
class Config:
    # ... existing fields, minus hsk_bootstrap_level ...
    language_settings: dict[str, dict] = field(default_factory=dict)
```

The dict is keyed by language code. Values are arbitrary key→value dicts:

```python
{"zh": {"bootstrap_level": 3}, "es": {"bootstrap_level": 0}}
```

The Config dataclass has zero knowledge of what keys exist inside each language's settings dict. That knowledge belongs to the language package.

### 2. config.yaml Serialization

`_config_to_dict()` nests `language_settings` under its own top-level key:

```yaml
language_settings:
  zh:
    bootstrap_level: 3
  es:
    bootstrap_level: 0
```

Remove `hsk_bootstrap_level` from both `_config_to_dict()` and `_dict_to_config()`. No migration — clean break. Users on the old format will see the default value (0) after upgrade and can set it again in the UI.

### 3. Language Package: Settings Adapter

Each language package defines its settings — schema and defaults — and registers them. The language service (which implements `LanguageProcessor`) reads its own settings. No other code knows about specific setting keys.

#### Registry extension

`register_language()` gains a `settings_schema` keyword argument:

```python
def register_language(
    code: str,
    *,
    ...
    settings_schema: list[dict] | None = None,
) -> None:
```

`settings_schema` is a list of field descriptors:

```python
[
    {
        "key": "bootstrap_level",
        "label": "HSK Bootstrap Level",
        "type": "select",
        "default": 0,
        "options": [
            {"value": 0, "label": "Off"},
            {"value": 1, "label": "HSK 1"},
            ...
        ],
        "hint": "Words ≤ this level are pre-marked known during mining.",
    }
]
```

| Key | Type | Description |
|-----|------|-------------|
| `key` | `str` | Unique key within the language's settings namespace |
| `label` | `str` | Display label in the UI |
| `type` | `str` | `"select"` or `"number"` |
| `default` | `any` | Default value when not configured |
| `options` | `list[{value, label}]` | For `"select"` type only |
| `hint` | `str` (optional) | Help text shown below the control |

New public factory function:

```python
def get_language_settings_schema(lang_code: str) -> list[dict]:
    """Return the settings schema registered for a language, or []."""
```

#### Chinese registration

```python
# languages/chinese/__init__.py
CHINESE_SETTINGS_SCHEMA = [
    {
        "key": "bootstrap_level",
        "label": "HSK Bootstrap Level",
        "type": "select",
        "default": 0,
        "options": [
            {"value": 0, "label": "Off"},
            {"value": 1, "label": "HSK 1"},
            {"value": 2, "label": "HSK 2"},
            {"value": 3, "label": "HSK 3"},
            {"value": 4, "label": "HSK 4"},
            {"value": 5, "label": "HSK 5"},
            {"value": 6, "label": "HSK 6"},
        ],
        "hint": "Words ≤ this level are pre-marked known during mining.",
    },
]

register_language(
    "zh",
    ...
    settings_schema=CHINESE_SETTINGS_SCHEMA,
)
```

### 4. Language Service Reads Its Own Settings

The `bootstrap_proficiency` signature changes: instead of `max_level: int`, it receives a plain `settings: dict` — a domain-safe dict that the service interprets itself:

```python
# domain/ports.py
class LanguageProcessor(ABC):
    def bootstrap_proficiency(
        self,
        vocab_repo: "VocabRepository",
        settings: dict,        # language-specific settings (plain dict, domain-safe)
        language_code: str,
    ) -> None:
        return  # default no-op
```

The Chinese service reads what it needs:

```python
# languages/chinese/service.py
def bootstrap_proficiency(self, vocab_repo, settings, language_code):
    max_level = int(settings.get("bootstrap_level", 0))
    if max_level < 1:
        return
    # ... rest unchanged
```

The pipeline passes the settings dict without knowing what's inside:

```python
# pipeline.py
lang = config.source_language
language_processor.bootstrap_proficiency(
    persistence,
    settings=config.language_settings.get(lang, {}),
    language_code=lang,
)
```

This is the key architectural win: `pipeline.py` has no idea that Chinese has a "bootstrap_level" or that Spanish has a "cefr_level". It just passes the dict. The language service owns its settings entirely.

### 5. API Changes

#### GET /api/languages

Add `settings_schema` to each language entry:

```json
{
  "languages": [
    {"code": "zh", "name": "Chinese", "settings_schema": [...]}
  ]
}
```

#### GET /api/config

Replace `hsk_bootstrap_level` with `language_settings`:

```json
{
  "source_language": "zh",
  "language_settings": {"zh": {"bootstrap_level": 3}},
  ...
}
```

#### PUT /api/config

Accept `language_settings`. Remove `hsk_bootstrap_level` from `ALLOWED`:

```python
ALLOWED = {
    "anki_connect_url", "source_language", "target_language",
    "translation_api", "sentence_gap_ms", "audio_pad_before_ms",
    "audio_pad_after_ms", "max_cards_per_video", "max_stash_cards",
    "deepl_api_key", "user_agent",
    "language_settings",
}
```

Deep-merge per-language when saving:

```python
if "language_settings" in data:
    for lang_code, settings in data["language_settings"].items():
        config.language_settings.setdefault(lang_code, {}).update(settings)
```

### 6. Frontend Changes

#### stores.svelte.js

Add `app.languageSettingsSchema = []`. `loadLanguages()` populates it from the language list. `selectLanguage()` updates it on switch. `saveConfig()` nests language-specific keys into `language_settings.<lang>`:

```javascript
export async function saveConfig(updates) {
    const globalUpdates = {};
    const langSettings = {};
    const schemaKeys = app.languageSettingsSchema.map(s => s.key);
    for (const [key, val] of Object.entries(updates)) {
        if (schemaKeys.includes(key)) {
            langSettings[key] = val;
        } else {
            globalUpdates[key] = val;
        }
    }
    if (Object.keys(langSettings).length > 0) {
        globalUpdates.language_settings = { [app.currentLanguage]: langSettings };
    }
    await api.updateConfig(globalUpdates);
    Object.assign(app.config, globalUpdates);
    // Merge language settings back
    if (globalUpdates.language_settings) {
        app.config.language_settings ??= {};
        Object.assign(
            app.config.language_settings[app.currentLanguage] ??= {},
            globalUpdates.language_settings[app.currentLanguage]
        );
    }
    addToast('Settings saved ✓', 'success', 2000);
}
```

#### SettingsPage.svelte

Dynamic language-specific section rendered from schema. Each `<option>` gets an explicit `selected={}` attribute — fixes the preselect bug:

```svelte
{#if app.languageSettingsSchema.length > 0}
  <section class="settings-section">
    <h3>Language-Specific: {app.currentLanguage}</h3>
    {#each app.languageSettingsSchema as field}
      <label>
        {field.label}
        {#if field.type === 'select'}
          <select name={field.key}>
            {#each field.options as opt}
              <option
                value={opt.value}
                selected={(app.config.language_settings?.[app.currentLanguage]?.[field.key] ?? field.default) === opt.value}
              >{opt.label}</option>
            {/each}
          </select>
        {:else if field.type === 'number'}
          <input type="number" name={field.key}
            value={app.config.language_settings?.[app.currentLanguage]?.[field.key] ?? field.default} />
        {/if}
        {#if field.hint}<span class="hint">{field.hint}</span>{/if}
      </label>
    {/each}
  </section>
{/if}
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/langmine/config.py` | Add `language_settings` field, remove `hsk_bootstrap_level`, update YAML serialize/deserialize |
| `src/langmine/domain/ports.py` | `bootstrap_proficiency` signature: `settings: dict` replaces `max_level: int` |
| `src/langmine/language_factory.py` | `register_language()` gains `settings_schema`, add `get_language_settings_schema()` |
| `src/langmine/languages/chinese/__init__.py` | Add `CHINESE_SETTINGS_SCHEMA` to `register_language()` call |
| `src/langmine/languages/chinese/service.py` | `bootstrap_proficiency` reads `settings.get("bootstrap_level", 0)` |
| `src/langmine/pipeline.py` | Pass `config.language_settings.get(lang, {})` to `bootstrap_proficiency` |
| `src/langmine/web/routes/config.py` | GET/PUT: `language_settings` in/out, `hsk_bootstrap_level` removed; GET /api/languages includes `settings_schema` |
| `src/langmine/web/frontend/src/lib/stores.svelte.js` | `languageSettingsSchema`, updated `saveConfig`/`loadLanguages`/`selectLanguage` |
| `src/langmine/web/frontend/src/lib/SettingsPage.svelte` | Dynamic language-specific section, fix preselect bug |
| Tests | Update config, pipeline, factory, API, and bootstrap tests |

## Edge Cases

- **No schema registered**: `get_language_settings_schema()` returns `[]`, UI renders nothing extra
- **Settings not in config yet**: Default from schema used; first save creates the entry
- **Language switch**: `selectLanguage()` updates `app.languageSettingsSchema`; Settings re-renders
- **PUT with empty `language_settings`**: No-op; existing settings preserved (deep-merge, not replace)
- **Unknown key in settings dict**: Language service ignores unknown keys (`settings.get(...)` with default)

## Verification

```bash
# Unit tests
pytest tests/test_config.py -v
pytest tests/test_language_factory.py -v
pytest tests/test_pipeline.py -v
pytest tests/test_web_api.py -v

# Bootstrap tests (Chinese)
pytest tests/languages/chinese/test_bootstrap.py -v

# Architecture checks
pytest tests/test_architecture.py -v

# Frontend build
cd src/langmine/web/frontend && npm run build

# Manual: open Settings, change bootstrap level, save, reload — verify preselected
# Manual: mine a video with bootstrap level > 0, verify words are marked known
```
