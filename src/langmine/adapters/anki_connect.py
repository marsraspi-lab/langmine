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
    '<div class="chinese">{{sentence_zh}}</div>{{#audio}}{{audio}}{{/audio}}'
)

_DEFAULT_BACK = (
    '<div class="chinese">{{sentence_zh}}</div>'
    "{{#audio}}{{audio}}{{/audio}}"
    '<hr id="answer">'
    '<div class="reading">{{sentence_reading}}</div>'
    '<div class="translation">{{translation}}</div>'
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
    ".reading { color: #2e7d32; font-style: italic; margin: 10px 0; }"
    ".translation { font-size: 22px; margin: 10px 0; }"
    ".word { color: #e53935; font-size: 18px; margin-top: 16px; }"
    ".screenshot { margin-top: 16px; }"
    ".screenshot img { max-width: 100%; border-radius: 4px; }"
)


def _cloze_wrap(text: str, unknown_word: str | None, is_cloze: bool) -> str:
    """Wrap the unknown word in cloze deletion syntax if cloze mode is active."""
    if not is_cloze or not unknown_word or unknown_word not in text:
        return text
    return text.replace(unknown_word, f"{{{{c1::{unknown_word}}}}}")


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

        try:
            self._export_setup_deck_and_model(
                deck_name, note_type_name,
                css=css, front=front, back=back,
                is_cloze=is_cloze, force_update_model=force_update_model,
            )
        except Exception as e:
            raise ConnectionError(
                f"AnkiConnect at {self._url} not reachable: {e}"
            ) from e

        # 4. Store audio + screenshot media first
        media_refs, screenshot_refs, media_errors = self._export_store_media(sentences)
        errors.extend(media_errors)

        # 5. Build notes
        notes = self._export_build_notes(
            sentences, media_refs, screenshot_refs,
            deck_name, note_type_name, is_cloze,
        )

        # 6-7. Deduplicate and add notes
        note_ids, added, duplicates = self._export_deduplicate_and_add(
            notes, errors
        )

        return {
            "note_ids": note_ids,
            "added": added,
            "duplicates": duplicates,
            "errors": errors,
        }

    def _export_build_notes(
        self,
        sentences: list[Sentence],
        media_refs: dict[int, str],
        screenshot_refs: dict[int, str],
        deck_name: str,
        note_type_name: str,
        is_cloze: bool,
    ) -> list[dict]:
        """Build Anki note dicts from sentences with media references."""
        notes = []
        for i, s in enumerate(sentences):
            audio_field = f"[sound:{media_refs[i]}]" if i in media_refs else ""
            screenshot_field = (
                f'<img src="{screenshot_refs[i]}">' if i in screenshot_refs else ""
            )
            if is_cloze and s.cloze_image_url:
                screenshot_field = f'<img src="{s.cloze_image_url}">'
            sentence_text = _cloze_wrap(s.text or "", s.unknown_word, is_cloze)
            notes.append(
                {
                    "deckName": deck_name,
                    "modelName": note_type_name,
                    "fields": {
                        "sentence_zh": sentence_text,
                        "sentence_reading": s.reading or "",
                        "translation": s.translation or "",
                        "unknown_word": s.unknown_word or "",
                        "audio": audio_field,
                        "screenshot": screenshot_field,
                    },
                    "tags": ["langmine"],
                }
            )
        return notes

    def _export_store_media(
        self,
        sentences: list[Sentence],
    ) -> tuple[dict[int, str], dict[int, str], list[str]]:
        """Store audio clips and screenshots. Returns (media_refs, screenshot_refs, errors)."""
        media_refs: dict[int, str] = {}
        screenshot_refs: dict[int, str] = {}
        errors: list[str] = []
        for i, s in enumerate(sentences):
            if s.audio_clip_path and os.path.exists(s.audio_clip_path):
                filename = f"langmine_{s.id or i}_{os.path.basename(s.audio_clip_path)}"
                try:
                    self._store_media(filename, s.audio_clip_path)
                    media_refs[i] = filename
                except Exception as e:
                    errors.append(f"Audio for sentence {s.id}: {e}")
            if s.screenshot_path and os.path.exists(s.screenshot_path):
                ss_name = f"langmine_ss_{s.id or i}_{os.path.basename(s.screenshot_path)}"
                try:
                    self._store_media(ss_name, s.screenshot_path)
                    screenshot_refs[i] = ss_name
                except Exception:
                    pass  # Screenshot is optional
        return media_refs, screenshot_refs, errors

    def _export_setup_deck_and_model(
        self,
        deck_name: str,
        note_type_name: str,
        *,
        css: str,
        front: str,
        back: str,
        is_cloze: bool,
        force_update_model: bool,
    ):
        """Ensure deck and note type exist; optionally force-update templates."""
        self._invoke("createDeck", {"deck": deck_name})
        self._create_model_if_missing(
            note_type_name, css=css, front=front, back=back, is_cloze=is_cloze
        )
        if force_update_model:
            self._update_model_templates(
                note_type_name, css=css, front=front, back=back, is_cloze=is_cloze
            )

    def _export_deduplicate_and_add(
        self,
        notes: list[dict],
        errors: list[str],
    ) -> tuple[list[int], int, int]:
        """Check duplicates, add non-duplicate notes. Returns (note_ids, added, duplicates)."""
        duplicates = 0
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

        note_ids: list[int] = []
        added = 0
        if new_notes:
            try:
                result = self._invoke("addNotes", {"notes": new_notes})
                note_ids = result.get("result", [])
                added = len(note_ids)
            except Exception as e:
                errors.append(f"Failed to add notes: {e}")

        return note_ids, added, duplicates

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

    def _create_model_if_missing(
        self,
        model_name: str,
        *,
        css: str,
        front: str,
        back: str,
        is_cloze: bool = False,
    ):
        """Create note type if it doesn't exist (idempotent)."""
        params = {
            "modelName": model_name,
            "inOrderFields": [
                "sentence_zh",
                "sentence_reading",
                "translation",
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

    def _update_model_templates(
        self,
        model_name: str,
        *,
        css: str,
        front: str,
        back: str,
        is_cloze: bool = False,
    ):
        """Force-update templates and CSS for an existing model.

        AnkiConnect's createModel is idempotent — it won't overwrite
        existing models. Call this after editing templates in config.yaml
        to push changes to Anki.
        """
        # Note: isCloze cannot be changed after model creation;
        # it's inherent to the model. The is_cloze parameter is
        # accepted but only used during model creation.
        _ = is_cloze
        self._invoke(
            "updateModelTemplates",
            {
                "model": {
                    "name": model_name,
                    "templates": {
                        "Card 1": {"Front": front, "Back": back},
                    },
                },
            },
        )
        self._invoke(
            "updateModelStyling",
            {
                "model": {
                    "name": model_name,
                    "css": css,
                },
            },
        )

    def _store_media(self, filename: str, filepath: str):
        """Upload a media file to Anki via base64."""
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        self._invoke(
            "storeMediaFile",
            {
                "filename": filename,
                "data": data,
            },
        )
