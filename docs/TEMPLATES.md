# Anki Card Template Customization

LangMine exports sentences to Anki as flashcards using the `LangMine Sentence` note type. Card templates (HTML + CSS) live as files in the language extension directory — one set per language. Customization is done by editing these files.

## Template Files Location

Each language has its own templates under `languages/<lang>/anki/`:

```
languages/chinese/anki/
├── basic/
│   ├── front.html   — Front of basic card
│   ├── back.html    — Back of basic card
│   └── css.css      — Styling for basic cards
└── cloze/
    ├── front.html   — Front of cloze deletion card
    ├── back.html    — Back of cloze deletion card
    └── css.css      — Styling for cloze cards
```

## How to Customize

1. **Edit the template files** in `languages/<lang>/anki/` directly.
2. **Push to Anki** — check "⚡ Update card templates" in the web UI sidebar, or use CLI:
   ```bash
   langmine export --all-kept --force-update-model
   ```
   This calls `updateModelTemplates` and `updateModelStyling` on the AnkiConnect API.

3. **Editing in Anki** — you can also edit directly in Anki: **Tools → Manage Note Types → "LangMine Sentence" → Cards...**. Changes in Anki survive future exports unless you check "⚡ Update card templates".

> **Note:** `force_update_model` only updates templates/CSS. To add or remove fields, delete the note type in Anki first (Tools → Manage Note Types → Delete), then re-export.

## Available Fields

These fields are available in Anki card templates. Use `{{fieldname}}` syntax:

| Field | Example | Description |
|-------|---------|-------------|
| `{{sentence_zh}}` | 你今天去哪儿 | The full sentence |
| `{{sentence_reading}}` | nǐ jīn tiān qù nǎr | Phonetic reading (pinyin for Chinese) |
| `{{translation_de}}` | Wohin gehst du heute | Translation |
| `{{unknown_word}}` | 哪儿 | The i+1 target word |
| `{{audio}}` | `[sound:langmine_1_clip.mp3]` | Embedded audio clip |
| `{{screenshot}}` | `<img src="...">` | Video frame at sentence midpoint |

## Conditional Blocks

Anki uses Mustache-style conditionals:

```
{{#unknown_word}}
  <div>New word: {{unknown_word}}</div>
{{/unknown_word}}
```

This only renders if `unknown_word` is non-empty.

```
{{#audio}}
  {{audio}}
{{/audio}}
```

Renders the audio player only when audio is available.

```
{{#screenshot}}
  {{screenshot}}
{{/screenshot}}
```

Renders the screenshot only when available.

## Default Basic Templates

**Front (`basic/front.html`):**
```html
<div class="chinese">{{sentence_zh}}</div>
{{#audio}}{{audio}}{{/audio}}
```

**Back (`basic/back.html`):**
```html
<div class="chinese">{{sentence_zh}}</div>
{{#audio}}{{audio}}{{/audio}}
<hr id="answer">
<div class="reading">{{sentence_reading}}</div>
<div class="translation">{{translation_de}}</div>
{{#unknown_word}}
<div class="word">🆕 {{unknown_word}}</div>
{{/unknown_word}}
{{#screenshot}}
<div class="screenshot">{{screenshot}}</div>
{{/screenshot}}
```

**CSS (`basic/css.css`):**
```css
.card { font-family: Arial, sans-serif; font-size: 20px; text-align: center; color: black; background-color: white; }
.chinese { font-size: 28px; margin: 20px 0; }
.reading { color: #2e7d32; font-style: italic; margin: 10px 0; }
.translation { font-size: 22px; margin: 10px 0; }
.word { color: #e53935; font-size: 18px; margin-top: 16px; }
.screenshot { margin-top: 16px; }
.screenshot img { max-width: 100%; border-radius: 4px; }
```

## Cloze Deletion Cards

Cloze cards use the `LangMine Cloze` note type (name from language manifest). Enable the "🕳️ Cloze deletion cards" checkbox in the web UI.

### Cloze Fields

| Field | Example | Description |
|-------|---------|-------------|
| `{{cloze:sentence_zh}}` | 你{{c1::今天}}去哪儿 | Sentence with unknown word hidden as cloze |
| `{{sentence_zh}}` | 你今天去哪儿 | Full sentence (shown on back) |
| `{{sentence_reading}}` | nǐ jīn tiān qù nǎr | Reading |
| `{{translation_de}}` | Wohin gehst du heute | Translation |
| `{{unknown_word}}` | 今天 | The cloze-hidden word |
| `{{audio}}` | `[sound:...]` | Audio clip |
| `{{screenshot}}` | `<img src="...">` | Video frame (hint on front) |

### Default Cloze Templates

**Front (`cloze/front.html`):**
```html
<div class="chinese">{{cloze:sentence_zh}}</div>
{{#audio}}{{audio}}{{/audio}}
{{#screenshot}}<div class="hint-img">{{screenshot}}</div>{{/screenshot}}
```

**Back (`cloze/back.html`):**
```html
<div class="chinese">{{sentence_zh}}</div>
{{#audio}}{{audio}}{{/audio}}
<hr id="answer">
<div class="reading">{{sentence_reading}}</div>
<div class="translation">{{translation_de}}</div>
<div>🆕 {{unknown_word}}</div>
{{#screenshot}}<div class="hint-img">{{screenshot}}</div>{{/screenshot}}
```

**CSS (`cloze/css.css`):**
```css
.card { font-family: Arial, sans-serif; font-size: 20px; }
.chinese { font-size: 28px; margin: 20px 0; }
.cloze { color: #e53935; font-weight: bold; }
.reading { color: #2e7d32; font-style: italic; }
.translation { font-size: 22px; }
.hint-img { margin-top: 12px; max-width: 100%; }
```

## Language-Specific Card Appearance

Each language can have completely different card styling. For example:
- **Chinese**: large font for characters, tone-colored readings
- **Spanish**: smaller font, no ruby annotations
- **Korean**: Hangul-friendly font stack

The template files in `languages/<lang>/anki/` are the source of truth — edit them directly.

## Adding Templates for a New Language

When creating a new language extension, include the `anki/` directory with both `basic/` and `cloze/` subdirectories. The `__init__.py` must expose a `get_anki_templates()` function that reads from these files:

```python
def get_anki_templates() -> dict:
    base = Path(__file__).parent / "anki"
    return {
        "basic_front": (base / "basic/front.html").read_text(),
        "basic_back": (base / "basic/back.html").read_text(),
        "basic_css": (base / "basic/css.css").read_text(),
        "cloze_front": (base / "cloze/front.html").read_text(),
        "cloze_back": (base / "cloze/back.html").read_text(),
        "cloze_css": (base / "cloze/css.css").read_text(),
    }
```

The `MANIFEST` dict in `__init__.py` sets `deck_name`, `note_type`, and `cloze_note_type` for the language.
