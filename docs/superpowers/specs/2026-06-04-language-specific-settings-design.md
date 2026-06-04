# Language-Specific Settings Design

**Date:** 2026-06-04
**Status:** Draft

## Context

The current `Config` dataclass and `config.yaml` are flat — all 24 fields are global. The `hsk_bootstrap_level` field lives under `mining:` in the YAML and appears in the Settings UI unconditionally, even though it's only meaningful for Chinese. When a second language (e.g. Spanish) is added, there is no mechanism for language-specific proficiency frameworks, Anki deck names, or mining defaults.

Additionally, the current `<select>` binding for `hsk_bootstrap_level` in `SettingsPage.svelte` is buggy — it uses Svelte one-way `value={}` on the `<select>` element without per-option `selected` attributes, so saved values are not preselected when the page loads.

## Goals

1. Config stores per-language settings in a `language_settings` dict keyed by language code
2. Each language package defines its own settings schema (fields, types, defaults, options) via the registry
3. The Settings UI renders language-specific controls dynamically from the schema, only for the active language
4. The pipeline reads per-language settings instead of hardcoded global fields
5. Fix the existing preselect and save bugs

## Non-Goals

- No per-language config files (settings stay in a single `config.yaml`)
- No UI for editing settings of non-active languages
- The `source_language` / `target_language` fields remain global (they select which language is active, not what the language's settings are)

---

## Design

### 1. Config Data Model

Add a single `language_settings` field to the `Config` dataclass:

```python
@dataclass
class Config:
    # ... existing 24 fields ...
    language_settings: dict[str, dict] = field(default_factory=dict)
```

The dict is keyed by language code (e.g. `"zh"`, `"es"`). Values are arbitrary key→value dicts — the schema is defined by each language package, not the Config dataclass. Example value:

```python
{"zh": {"bootstrap_level": 3}, "es": {"bootstrap_level": 0}}
```

### 2. config.yaml Serialization

The `_config_to_dict()` function nests `language_settings` under its own top-level key:

```yaml
language_settings:
  zh:
    bootstrap_level: 3
  es:
    bootstrap_level: 0
```

`_dict_to_config()` reads it back. Both already use deep-merge — the new key is additive.

#### Migration

`load_config()` auto-migrates: if the old `mining.hsk_bootstrap_level` key exists in the YAML and `language_settings.zh.bootstrap_level` does not, copy the value over. The old `hsk_bootstrap_level` field remains on the dataclass (deprecated but not removed) and is no longer returned by `GET /api/config` or accepted by `PUT /api/config`. It is only used for the one-time migration.

### 3. Language Registry Extension

`register_language()` gains a `settings_schema` keyword argument:

```python
def register_language(
    code: str,
    *,
    name: str,
    service_class: type[LanguageProcessor],
    dictionary_class: type[Dictionary],
    frequency_class: type[FrequencySource],
    transcript_languages: list[str],
    manifest: dict | None = None,
    get_anki_templates: Callable[[], dict] | None = None,
    get_proficiency_level: Callable[[str], int | None] | None = None,
    settings_schema: list[dict] | None = None,   # NEW
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
            {"value": 2, "label": "HSK 2"},
            {"value": 3, "label": "HSK 3"},
            {"value": 4, "label": "HSK 4"},
            {"value": 5, "label": "HSK 5"},
            {"value": 6, "label": "HSK 6"},
        ],
        "hint": "Words ≤ this level are pre-marked known during mining.",
    }
]
```

Field descriptor keys:

| Key | Type | Description |
|-----|------|-------------|
| `key` | `str` | Unique key within the language's settings namespace |
| `label` | `str` | Display label in the UI |
| `type` | `str` | `"select"` or `"number"` (extensible later) |
| `default` | `any` | Default value when not configured |
| `options` | `list[{value, label}]` | For `"select"` type — the available choices |
| `hint` | `str` (optional) | Help text shown below the control |

A new public function exposes the schema:

```python
def get_language_settings_schema(lang_code: str) -> list[dict]:
    """Return the settings schema registered for a language, or []."""
    if not lang_code:
        return []
    _ensure_loaded(lang_code)
    return _LANGUAGE_REGISTRY[lang_code].get("settings_schema", [])
```

### 4. API Changes

#### GET /api/languages

Add `settings_schema` to each language entry:

```json
{
  "languages": [
    {
      "code": "zh",
      "name": "Chinese",
      "settings_schema": [
        {"key": "bootstrap_level", "label": "HSK Bootstrap Level", ...}
      ]
    }
  ]
}
```

#### GET /api/config

Replace flat `hsk_bootstrap_level` with `language_settings`:

```json
{
  "anki_connect_url": "...",
  "source_language": "zh",
  "language_settings": {
    "zh": {"bootstrap_level": 3}
  },
  ...
}
```

#### PUT /api/config

Accept `language_settings` in the body. Deep-merge into existing `config.language_settings`. Remove `hsk_bootstrap_level` from `ALLOWED`.

```python
ALLOWED = {
    "anki_connect_url", "source_language", "target_language",
    "translation_api", "sentence_gap_ms", "audio_pad_before_ms",
    "audio_pad_after_ms", "max_cards_per_video", "max_stash_cards",
    "deepl_api_key", "user_agent",
    "language_settings",  # NEW
}
# hsk_bootstrap_level removed from ALLOWED
```

When `language_settings` is present in the PUT body, deep-merge per-language:

```python
if "language_settings" in data:
    for lang_code, settings in data["language_settings"].items():
        config.language_settings.setdefault(lang_code, {}).update(settings)
```

### 5. Pipeline Change

In `pipeline.py`, replace the hardcoded config read:

```python
# Before:
max_level = int(config.hsk_bootstrap_level)

# After:
lang = config.source_language
lang_settings = config.language_settings.get(lang, {})
max_level = int(lang_settings.get("bootstrap_level", 0))
```

### 6. Frontend Changes

#### stores.svelte.js

Add `app.languageSettingsSchema = []` (populated by `loadLanguages()`). Update `loadLanguages()` to extract `settings_schema`:

```javascript
export async function loadLanguages() {
    const data = await api.listLanguages();
    app.languages.splice(0, app.languages.length, ...data.languages);
    // Store schema for the current language
    const current = data.languages.find(l => l.code === app.currentLanguage);
    app.languageSettingsSchema = current?.settings_schema || [];
}
```

Update `saveConfig()` to nest language-specific settings:

```javascript
export async function saveConfig(updates) {
    // Extract language-specific keys and nest them
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
        globalUpdates.language_settings = {
            [app.currentLanguage]: langSettings
        };
    }
    await api.updateConfig(globalUpdates);
    // Merge back into local config
    Object.assign(app.config, globalUpdates);
    if (globalUpdates.language_settings) {
        const ls = globalUpdates.language_settings[app.currentLanguage];
        Object.assign(app.config.language_settings?.[app.currentLanguage] ?? {}, ls);
    }
    addToast('Settings saved ✓', 'success', 2000);
}
```

#### SettingsPage.svelte

Add a dynamic language-specific section that renders from `app.languageSettingsSchema`. The section only appears when the schema is non-empty:

```svelte
{#if app.languageSettingsSchema.length > 0}
  <section class="settings-section">
    <h3>Language-Specific: {app.currentLanguage}</h3>
    {#each app.languageSettingsSchema as field}
      <label>
        {field.label}
        {#if field.type === 'select'}
          <select
            name={field.key}
            value={app.config.language_settings?.[app.currentLanguage]?.[field.key] ?? field.default}
          >
            {#each field.options as opt}
              <option
                value={opt.value}
                selected={(app.config.language_settings?.[app.currentLanguage]?.[field.key] ?? field.default) === opt.value}
              >{opt.label}</option>
            {/each}
          </select>
        {:else if field.type === 'number'}
          <input
            type="number"
            name={field.key}
            value={app.config.language_settings?.[app.currentLanguage]?.[field.key] ?? field.default}
          />
        {/if}
        {#if field.hint}
          <span class="hint">{field.hint}</span>
        {/if}
      </label>
    {/each}
  </section>
{/if}
```

Key fix: each `<option>` gets an explicit `selected={}` attribute, fixing the preselect bug. The value path reads from `language_settings.<lang>.<key>` instead of a flat config key.

### 7. Chinese Package Registration

```python
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
    name="Chinese",
    ...
    settings_schema=CHINESE_SETTINGS_SCHEMA,
)
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/langmine/config.py` | Add `language_settings` field, migration logic, deprecate `hsk_bootstrap_level` |
| `src/langmine/language_factory.py` | `register_language()` + `settings_schema`, add `get_language_settings_schema()` |
| `src/langmine/languages/chinese/__init__.py` | Add `CHINESE_SETTINGS_SCHEMA` to `register_language()` call |
| `src/langmine/web/routes/config.py` | GET/PUT include `language_settings`, remove `hsk_bootstrap_level`; GET /api/languages includes `settings_schema` |
| `src/langmine/pipeline.py` | Read `bootstrap_level` from `config.language_settings[lang]` |
| `src/langmine/web/frontend/src/lib/stores.svelte.js` | `languageSettingsSchema`, updated `saveConfig`, `loadLanguages` |
| `src/langmine/web/frontend/src/lib/SettingsPage.svelte` | Dynamic language-specific section, fix preselect bug |
| Tests | Update config, pipeline, API, and factory tests |

Additionally, `selectLanguage()` must update the schema when switching languages:

```javascript
export async function selectLanguage(code) {
    if (code === app.currentLanguage) return;
    // ...
    app.currentLanguage = code;
    app.config.source_language = code;
    // Update schema for the new language
    const lang = app.languages.find(l => l.code === code);
    app.languageSettingsSchema = lang?.settings_schema || [];
    // ...
}
```

## Edge Cases

- **No schema registered**: `get_language_settings_schema()` returns `[]`, UI renders nothing extra
- **Settings not in config yet**: Default from schema used; first save creates the entry
- **Language switch**: `selectLanguage()` updates `app.languageSettingsSchema` to the new language's schema; Settings UI re-renders
- **Old `hsk_bootstrap_level` in YAML**: Migrated once on `load_config()`, then ignored
- **PUT with empty `language_settings`**: No-op; existing settings preserved (deep-merge, not replace)

## Verification

```bash
# Unit tests
pytest tests/test_config.py -v
pytest tests/test_language_factory.py -v
pytest tests/test_pipeline.py -v
pytest tests/test_web_api.py -v

# Architecture checks
pytest tests/test_architecture.py -v

# Frontend build
cd src/langmine/web/frontend && npm run build

# Manual: open Settings page, change bootstrap level, save, reload — verify preselected
# Manual: mine a video with bootstrap level > 0, verify words are marked known
```
