# Anki Card Template Customization

LangMine exports sentences to Anki as flashcards using the `LangMine Sentence`
note type. You can customize how cards look either in Anki directly, or
via `~/.langmine/config.yaml` (pushed on next export).

## Available Fields

These fields are available in Anki card templates. Use `{{fieldname}}` syntax:

| Field | Example | Description |
|-------|---------|-------------|
| `{{sentence_zh}}` | 你今天去哪儿 | The full Chinese sentence |
| `{{sentence_pinyin}}` | nǐ jīn tiān qù nǎr | Pinyin reading of the sentence |
| `{{translation_de}}` | Wohin gehst du heute | German translation |
| `{{unknown_word}}` | 哪儿 | The i+1 target word (the one new word) |
| `{{audio}}` | [sound:langmine_1_clip.mp3] | Embedded audio clip. Use conditional: `{{#audio}}{{audio}}{{/audio}}` |

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

## Customizing in Anki

After the first export creates the note type:

1. Open Anki → **Tools → Manage Note Types**
2. Select **"LangMine Sentence"** → **Cards...**
3. Edit the **Front Template**, **Back Template**, and **Styling** (CSS)
4. Changes take effect immediately for all existing and future cards

## Customizing via config.yaml

Edit `~/.langmine/config.yaml` to set default templates. Changes are
pushed on the next export:

```yaml
anki:
  anki_connect_url: "http://localhost:8765"
  deck_name: "Chinese::Sentence Mining"
  note_type: "LangMine Sentence"
  card_css: |
    .card { font-family: 'Noto Sans SC', sans-serif; font-size: 22px; }
    .chinese { font-size: 32px; margin: 20px 0; }
    .pinyin { color: #2e7d32; font-style: italic; }
    .translation { font-size: 24px; }
    .word { color: #e53935; margin-top: 16px; }

  card_front_template: |
    <div class="chinese">{{sentence_zh}}</div>
    {{#audio}}{{audio}}{{/audio}}

  card_back_template: |
    <div class="chinese">{{sentence_zh}}</div>
    {{#audio}}{{audio}}{{/audio}}
    <hr id="answer">
    <div class="pinyin">{{sentence_pinyin}}</div>
    <div class="translation">{{translation_de}}</div>
    {{#unknown_word}}
      <div class="word">🆕 {{unknown_word}}</div>
    {{/unknown_word}}
```

To push updated templates to Anki:
- **Web UI:** check "⚡ Update card templates" before clicking Export
- **CLI:** `langmine export --all-kept --force-update-model`

> **Note:** The `force_update_model` flag only updates templates/CSS.
> To add or remove fields, you must delete the note type in Anki first
> (Tools → Manage Note Types → Delete), then re-export.

## Default Template

The default card looks like this:

**Front:**
```
  你今天去哪儿
  🔊 [audio player]
```

**Back:**
```
  你今天去哪儿
  🔊 [audio player]
  ────────────────
  nǐ jīn tiān qù nǎr
  Wohin gehst du heute
  🆕 哪儿
```
