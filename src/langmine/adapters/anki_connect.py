"""AnkiConnect adapter — sends cards directly to Anki via HTTP API.

AnkiConnect is an Anki addon (ID: 2055492159) that exposes a JSON-RPC API
on localhost:8765. Install it in Anki: Tools → Add-ons → Get Add-ons.

Protocol: POST http://localhost:8765 with {"action": "...", "version": 6, "params": {...}}
"""

import base64
import os

import requests

from langmine.domain.models import Sentence
from langmine.domain.ports import AnkiExporter


class AnkiConnectAdapter(AnkiExporter):
    """Export sentences to Anki via AnkiConnect HTTP API."""

    def __init__(self, url: str = "http://localhost:8765"):
        self._url = url

    def export(
        self,
        sentences: list[Sentence],
        deck_name: str = "Chinese::Sentence Mining",
        note_type_name: str = "LangMine Sentence",
    ) -> dict:
        if not sentences:
            raise ValueError("No sentences to export")

        errors: list[str] = []
        added = 0
        duplicates = 0
        note_ids: list[int] = []

        try:
            # 1. Ensure deck exists (idempotent)
            self._invoke("createDeck", {"deck": deck_name})

            # 2. Ensure note type exists (idempotent)
            self._create_model_if_missing(note_type_name)

        except Exception as e:
            raise ConnectionError(
                f"AnkiConnect at {self._url} not reachable: {e}"
            ) from e

        # 3. Store audio media first (before note creation)
        media_refs: dict[int, str] = {}
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

        # 4. Build notes
        notes = []
        for i, s in enumerate(sentences):
            audio_field = (
                f"[sound:{media_refs[i]}]" if i in media_refs else ""
            )
            notes.append({
                "deckName": deck_name,
                "modelName": note_type_name,
                "fields": {
                    "sentence_zh": s.text or "",
                    "sentence_pinyin": s.pinyin or "",
                    "translation_de": s.translation_de or "",
                    "unknown_word": s.unknown_word or "",
                    "audio": audio_field,
                },
                "tags": ["langmine"],
            })

        # 5. Check for duplicates
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
            pass  # If canAddNotes fails, try adding all

        # 6. Add non-duplicate notes
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

    def _create_model_if_missing(self, model_name: str):
        """Create note type if it doesn't exist (idempotent)."""
        self._invoke("createModel", {
            "modelName": model_name,
            "inOrderFields": [
                "sentence_zh",
                "sentence_pinyin",
                "translation_de",
                "unknown_word",
                "audio",
            ],
            "css": (
                ".card { font-family: Arial, sans-serif; font-size: 20px; "
                "text-align: center; color: black; background-color: white; }"
                ".chinese { font-size: 28px; margin: 20px 0; }"
                ".pinyin { color: #2e7d32; font-style: italic; margin: 10px 0; }"
                ".translation { font-size: 22px; margin: 10px 0; }"
                ".word { color: #e53935; font-size: 18px; margin-top: 16px; }"
            ),
            "cardTemplates": [
                {
                    "Name": "Card 1",
                    "Front": (
                        '<div class="chinese">{{sentence_zh}}</div>'
                        "{{#audio}}{{audio}}{{/audio}}"
                    ),
                    "Back": (
                        '<div class="chinese">{{sentence_zh}}</div>'
                        "{{#audio}}{{audio}}{{/audio}}"
                        '<hr id="answer">'
                        '<div class="pinyin">{{sentence_pinyin}}</div>'
                        '<div class="translation">{{translation_de}}</div>'
                        "{{#unknown_word}}"
                        '<div class="word">🆕 {{unknown_word}}</div>'
                        "{{/unknown_word}}"
                    ),
                },
            ],
        })

    def _store_media(self, filename: str, filepath: str):
        """Upload a media file to Anki via base64."""
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        self._invoke("storeMediaFile", {
            "filename": filename,
            "data": data,
        })
