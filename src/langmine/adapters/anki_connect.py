"""AnkiConnect adapter — sends cards directly to Anki via HTTP API.

AnkiConnect is an Anki addon (ID: 2055492159) that exposes a JSON-RPC API
on localhost:8765. Install it in Anki: Tools → Add-ons → Get Add-ons.

Protocol: POST http://localhost:8765 with {"action": "...", "version": 6, "params": {...}}

Card templates are configurable via ~/.langmine/config.yaml under the
`anki` key. See docs/TEMPLATES.md for available fields and Anki template syntax.
"""

import base64
import os

import requests

from langmine.domain.models import Sentence
from langmine.domain.ports import AnkiExporter


# Default templates (fallback if not in config)
_DEFAULT_FRONT = (
    '<div class="chinese">{{sentence_zh}}</div>'
    "{{#audio}}{{audio}}{{/audio}}"
)

_DEFAULT_BACK = (
    '<div class="chinese">{{sentence_zh}}</div>'
    "{{#audio}}{{audio}}{{/audio}}"
    '<hr id="answer">'
    '<div class="pinyin">{{sentence_pinyin}}</div>'
    '<div class="translation">{{translation_de}}</div>'
    "{{#unknown_word}}"
    '<div class="word">🆕 {{unknown_word}}</div>'
    "{{/unknown_word}}"
    "{{#screenshot}}"
    '<div class="screenshot">{{screenshot}}</div>'
    "{{/screenshot}}"
)

_DEFAULT_CSS = (
    ".card { font-family: Arial, sans-serif; font-size: 20px; "
    "text-align: center; color: black; background-color: white; }"
    ".chinese { font-size: 28px; margin: 20px 0; }"
    ".pinyin { color: #2e7d32; font-style: italic; margin: 10px 0; }"
    ".translation { font-size: 22px; margin: 10px 0; }"
    ".word { color: #e53935; font-size: 18px; margin-top: 16px; }"
    ".screenshot { margin-top: 16px; }"
    ".screenshot img { max-width: 100%; border-radius: 4px; }"
)


class AnkiConnectAdapter(AnkiExporter):
    """Export sentences to Anki via AnkiConnect HTTP API."""

    def __init__(self, url: str = "http://localhost:8765"):
        self._url = url

    def export(
        self,
        sentences: list[Sentence],
        deck_name: str = "Chinese::Sentence Mining",
        note_type_name: str = "LangMine Sentence",
        card_css: str | None = None,
        card_front: str | None = None,
        card_back: str | None = None,
        force_update_model: bool = False,
        card_type: str = "basic",
    ) -> dict:
        """Export sentences to Anki.

        Args:
            sentences: Sentences to export.
            deck_name: Anki deck name.
            note_type_name: Anki note type name.
            card_css: CSS for card styling (falls back to default).
            card_front: Front template HTML (falls back to default).
            card_back: Back template HTML (falls back to default).
            force_update_model: If True, update templates even if model
                already exists. Use after editing templates in config.yaml.
            card_type: "basic" for normal cards, "cloze" for cloze deletion.
                Cloze mode wraps the unknown word in {{c1::...}} and
                uses Anki's cloze note type (isCloze=True).

        Returns:
            Dict with note_ids, added, duplicates, errors.
        """
        if not sentences:
            raise ValueError("No sentences to export")

        css = card_css or _DEFAULT_CSS
        front = card_front or _DEFAULT_FRONT
        back = card_back or _DEFAULT_BACK
        is_cloze = card_type == "cloze"

        errors: list[str] = []
        added = 0
        duplicates = 0
        note_ids: list[int] = []

        try:
            # 1. Ensure deck exists (idempotent)
            self._invoke("createDeck", {"deck": deck_name})

            # 2. Ensure note type exists
            self._create_model_if_missing(
                note_type_name, css=css, front=front, back=back,
                is_cloze=is_cloze,
            )

            # 3. Force-update templates if requested
            if force_update_model:
                self._update_model_templates(
                    note_type_name, css=css, front=front, back=back,
                    is_cloze=is_cloze,
                )

        except Exception as e:
            raise ConnectionError(
                f"AnkiConnect at {self._url} not reachable: {e}"
            ) from e

        # 4. Store audio + screenshot media first
        media_refs: dict[int, str] = {}
        screenshot_refs: dict[int, str] = {}
        for i, s in enumerate(sentences):
            if s.audio_clip_path and os.path.exists(s.audio_clip_path):
                filename = (
                    f"langmine_{s.id or i}_"
                    f"{os.path.basename(s.audio_clip_path)}"
                )
                try:
                    self._store_media(filename, s.audio_clip_path)
                    media_refs[i] = filename
                except Exception as e:
                    errors.append(f"Audio for sentence {s.id}: {e}")

            # Upload screenshot if available
            if s.screenshot_path and os.path.exists(s.screenshot_path):
                ss_name = (
                    f"langmine_ss_{s.id or i}_"
                    f"{os.path.basename(s.screenshot_path)}"
                )
                try:
                    self._store_media(ss_name, s.screenshot_path)
                    screenshot_refs[i] = ss_name
                except Exception as e:
                    pass  # Screenshot is optional

        # 5. Build notes
        notes = []
        for i, s in enumerate(sentences):
            audio_field = (
                f"[sound:{media_refs[i]}]" if i in media_refs else ""
            )
            screenshot_field = (
                f'<img src="{screenshot_refs[i]}">'
                if i in screenshot_refs else ""
            )
            # Build sentence_zh field — for cloze, wrap unknown word
            sentence_text = s.text or ""
            if is_cloze and s.unknown_word and s.unknown_word in sentence_text:
                sentence_text = sentence_text.replace(
                    s.unknown_word, f"{{{{c1::{s.unknown_word}}}}}"
                )

            notes.append({
                "deckName": deck_name,
                "modelName": note_type_name,
                "fields": {
                    "sentence_zh": sentence_text,
                    "sentence_pinyin": s.pinyin or "",
                    "translation_de": s.translation_de or "",
                    "unknown_word": s.unknown_word or "",
                    "audio": audio_field,
                    "screenshot": screenshot_field,
                },
                "tags": ["langmine"],
            })

        # 6. Check for duplicates
        new_notes = notes
        try:
            dup_result = self._invoke("canAddNotes", {"notes": notes})
            dupes = dup_result.get("result", [])
            new_notes = []
            for j, dup in enumerate(dupes):
                if dup is None:
                    new_notes.append(notes[j])
                else:
                    duplicates += 1
        except Exception:
            pass

        # 7. Add non-duplicate notes
        if new_notes:
            try:
                result = self._invoke("addNotes", {"notes": new_notes})
                note_ids = result.get("result", [])
                added = len(note_ids)
            except Exception as e:
                errors.append(f"Failed to add notes: {e}")

        return {
            "note_ids": note_ids,
            "added": added,
            "duplicates": duplicates,
            "errors": errors,
        }

    def _invoke(self, action: str, params: dict | None = None) -> dict:
        """Call an AnkiConnect action via JSON-RPC."""
        payload = {
            "action": action,
            "version": 6,
            "params": params or {},
        }
        resp = requests.post(self._url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"AnkiConnect error: {data['error']}")
        return data

    def _create_model_if_missing(self, model_name: str, *, css: str,
                                  front: str, back: str, is_cloze: bool = False):
        """Create note type if it doesn't exist (idempotent)."""
        params = {
            "modelName": model_name,
            "inOrderFields": [
                "sentence_zh",
                "sentence_pinyin",
                "translation_de",
                "unknown_word",
                "audio",
                "screenshot",
            ],
            "css": css,
            "cardTemplates": [
                {"Name": "Card 1", "Front": front, "Back": back},
            ],
        }
        if is_cloze:
            params["isCloze"] = True
        self._invoke("createModel", params)

    def _update_model_templates(self, model_name: str, *, css: str,
                                  front: str, back: str, is_cloze: bool = False):
        """Force-update templates and CSS for an existing model.

        AnkiConnect's createModel is idempotent — it won't overwrite
        existing models. Call this after editing templates in config.yaml
        to push changes to Anki.
        """
        # Note: isCloze cannot be changed after model creation;
        # it's inherent to the model. The is_cloze parameter is
        # accepted but only used during model creation.
        _ = is_cloze
        self._invoke("updateModelTemplates", {
            "model": {
                "name": model_name,
                "templates": {
                    "Card 1": {"Front": front, "Back": back},
                },
            },
        })
        self._invoke("updateModelStyling", {
            "model": {
                "name": model_name,
                "css": css,
            },
        })

    def _store_media(self, filename: str, filepath: str):
        """Upload a media file to Anki via base64."""
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        self._invoke("storeMediaFile", {
            "filename": filename,
            "data": data,
        })
