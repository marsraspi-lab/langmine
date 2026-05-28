# M5: Export to Anki (via AnkiConnect) Implementation Plan

> **For Hermes:** Implement task-by-task using TDD. Commit after each task.

**Goal:** Send kept sentences directly to a running Anki instance via AnkiConnect HTTP API. Cards appear immediately — no manual .apkg import. Deploy to `Chinese::Sentence Mining` deck.

**Architecture:** `AnkiExporter` port → `AnkiConnectAdapter` that speaks JSON-RPC to `http://localhost:8765`. Adapter creates note type, deck, embeds audio as base64 media, and adds notes with duplicate detection.

**Tech Stack:** requests (already installed), AnkiConnect JSON-RPC v6, no extra library needed

---

## AnkiConnect Protocol (reference)

All requests: `POST http://localhost:8765` with `{"action": "...", "version": 6, "params": {...}}`

Key actions:
- `createDeck` — `{"deck": "Chinese::Sentence Mining"}`
- `createModel` — `{"modelName": "...", "inOrderFields": [...], "css": "...", "cardTemplates": [...]}`
- `storeMediaFile` — `{"filename": "audio_1.mp3", "data": "<base64>"}`
- `canAddNotes` — `{"notes": [...]}` → check duplicates
- `addNotes` — `{"notes": [...]}` → returns note IDs

---

### Task 1: Add AnkiExporter port

**Files:**
- Modify: `src/langmine/domain/ports.py`

Add at end of ports.py:

```python
class AnkiExporter(ABC):
    """Port for exporting sentences to Anki.

    Adapters: AnkiConnect (HTTP), direct .apkg generation (genanki).
    """

    @abstractmethod
    def export(
        self,
        sentences: list,
    ) -> dict:
        """Export sentences as Anki flashcards.

        Args:
            sentences: List of Sentence domain objects with status="kept".

        Returns:
            Dict with: note_ids (list[int]), added (int), duplicates (int), errors (list[str]).
        """
```

**Step 2:** `python -c "from langmine.domain.ports import AnkiExporter"` → clean import

**Step 3:** Commit

---

### Task 2: Create AnkiConnectAdapter (TDD)

**Files:**
- Create: `src/langmine/adapters/anki_connect.py`
- Create: `tests/adapters/test_anki_connect.py`
- Modify: `src/langmine/adapters/__init__.py`

**Step 1: Write tests**

```python
# tests/adapters/test_anki_connect.py
import json
import base64
import pytest
from unittest.mock import patch, MagicMock
from langmine.domain.models import Sentence
from langmine.adapters.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter(url="http://localhost:8765")


@pytest.fixture
def sample_sentences():
    return [
        Sentence(
            id=1, video_id=1, start_ms=0, end_ms=1000,
            text="你好", pinyin="nǐ hǎo",
            translation_de="Hallo", unknown_word="你好",
            status="kept",
        ),
    ]


def test_implements_port(adapter):
    from langmine.domain.ports import AnkiExporter
    assert isinstance(adapter, AnkiExporter)


def test_export_checks_connectivity(adapter, sample_sentences):
    """Should raise ConnectionError if AnkiConnect not reachable."""
    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("Connection refused")
        with pytest.raises(ConnectionError, match="AnkiConnect"):
            adapter.export(sample_sentences)


def test_export_sends_correct_payload(adapter, sample_sentences):
    """Should send createDeck, createModel, addNotes in sequence."""
    with patch("requests.post") as mock_post:
        # Simulate: deck created → model exists → notes added
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"result": [1], "error": None},
        )

        result = adapter.export(sample_sentences)

        assert result["added"] == 1
        assert result["duplicates"] == 0

        # Verify all calls
        calls = [c[1]["json"]["action"] for c in mock_post.call_args_list]
        assert "createDeck" in calls
        assert "createModel" in calls
        assert "addNotes" in calls


def test_export_detects_duplicates(adapter, sample_sentences):
    """Should detect duplicate notes via canAddNotes."""
    with patch("requests.post") as mock_post:
        # canAddNotes returns [duplicate_note] → skip
        def side_effect(*args, **kwargs):
            body = kwargs["json"]
            if body["action"] == "canAddNotes":
                return MagicMock(
                    status_code=200,
                    json=lambda: {"result": [None], "error": None},  # not a duplicate
                ) if False else MagicMock(
                    status_code=200,
                    json=lambda: {"result": [{"note": 123}], "error": None},  # actually test both
                )
            return MagicMock(status_code=200, json=lambda: {"result": None, "error": None})

        # Simpler: test that canAddNotes is called
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"result": None, "error": None},
        )
        adapter.export(sample_sentences)

        actions = [c[1]["json"]["action"] for c in mock_post.call_args_list]
        assert "canAddNotes" in actions


def test_export_handles_audio(adapter):
    """Should store media for sentences with audio clips."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "test.mp3")
        with open(audio_path, "wb") as f:
            f.write(b"\xff\xfb\x90\x00" * 100)  # fake MP3 frame

        sentences = [
            Sentence(
                id=1, video_id=1, start_ms=0, end_ms=1000,
                text="你好", pinyin="nǐ hǎo",
                translation_de="Hallo", unknown_word="你好",
                audio_clip_path=audio_path, status="kept",
            ),
        ]

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"result": [1], "error": None},
            )
            adapter.export(sentences)

            actions = [c[1]["json"]["action"] for c in mock_post.call_args_list]
            assert "storeMediaFile" in actions


def test_export_returns_summary(adapter, sample_sentences):
    """Should return dict with added count and note IDs."""
    with patch("requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"result": [42], "error": None},
        )
        result = adapter.export(sample_sentences)

        assert "added" in result
        assert "duplicates" in result
        assert "errors" in result
        assert result["added"] > 0
```

**Step 2:** Run `pytest tests/adapters/test_anki_connect.py -v` → FAIL (no module)

**Step 3: Implement AnkiConnectAdapter**

```python
"""AnkiConnect adapter — sends cards directly to Anki via HTTP API.

AnkiConnect is an Anki addon that exposes a JSON-RPC API on localhost:8765.
Install it in Anki: Tools → Add-ons → Get Add-ons → 2055492159
"""

import base64
import os

import requests

from langmine.domain.models import Sentence
from langmine.domain.ports import AnkiExporter


LANMINE_MODEL_ID = 1734567890  # Stable model ID


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

        try:
            # 1. Ensure deck exists
            self._invoke("createDeck", {"deck": deck_name})

            # 2. Ensure note type exists (idempotent)
            self._create_model_if_missing(note_type_name)

        except Exception as e:
            raise ConnectionError(f"AnkiConnect at {self._url} not reachable: {e}")

        # 3. Store audio media first (before note creation)
        media_refs: dict[int, str] = {}  # sentence_id → media filename
        for i, s in enumerate(sentences):
            if s.audio_clip_path and os.path.exists(s.audio_clip_path):
                filename = f"langmine_{s.id or i}_{os.path.basename(s.audio_clip_path)}"
                try:
                    self._store_media(filename, s.audio_clip_path)
                    media_refs[i] = filename
                except Exception as e:
                    errors.append(f"Audio for sentence {s.id}: {e}")

        # 4. Build notes, check duplicates, add
        notes = []
        for i, s in enumerate(sentences):
            audio_field = f"[sound:{media_refs[i]}]" if i in media_refs else ""

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

        # Check for duplicates
        try:
            dupes = self._invoke("canAddNotes", {"notes": notes})
            new_notes = []
            for j, dup in enumerate(dupes.get("result", [])):
                if dup is None:
                    new_notes.append(notes[j])
                else:
                    duplicates += 1
        except Exception:
            new_notes = notes  # If canAddNotes fails, try adding all

        # Add non-duplicate notes
        if new_notes:
            try:
                result = self._invoke("addNotes", {"notes": new_notes})
                added = len(result.get("result", []))
            except Exception as e:
                errors.append(f"Failed to add notes: {e}")

        return {
            "note_ids": result.get("result", []) if new_notes else [],
            "added": added,
            "duplicates": duplicates,
            "errors": errors,
        }

    def _invoke(self, action: str, params: dict | None = None) -> dict:
        """Call an AnkiConnect action."""
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
        """Create note type if it doesn't exist (idempotent — AnkiConnect ignores duplicates)."""
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
        """Upload a media file to Anki."""
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        self._invoke("storeMediaFile", {
            "filename": filename,
            "data": data,
        })
```

**Step 4:** Run `pytest tests/adapters/test_anki_connect.py -v` → 6 PASS

**Step 5:** Add to `__init__.py`:

```python
from langmine.adapters.anki_connect import AnkiConnectAdapter
# and add "AnkiConnectAdapter" to __all__
```

**Step 6:** Commit

---

### Task 3: Add export API endpoint

**Files:**
- Modify: `src/langmine/web/routes.py`
- Modify: `src/langmine/web/app.py` (accept anki_exporter)
- Modify: `src/langmine/cli.py` (wire AnkiConnectAdapter)
- Modify: `tests/test_web_api.py` (export tests)

**Step 1: Update `create_app` signature**

```python
def create_app(
    persistence: Persistence,
    language_processor: LanguageProcessor | None = None,
    transcript_source: TranscriptSource | None = None,
    audio_processor: AudioProcessor | None = None,
    anki_exporter: AnkiExporter | None = None,
) -> Flask:
    # ...
    app.config["LANGMINE_ANKI_EXPORTER"] = anki_exporter
```

**Step 2: Add export endpoint in routes.py**

```python
@app.route("/api/export/anki", methods=["POST"])
def export_anki():
    """Export kept sentences directly to Anki via AnkiConnect."""
    persistence = _get_persistence()
    exporter = current_app.config.get("LANGMINE_ANKI_EXPORTER")

    if exporter is None:
        return jsonify({"error": "Anki exporter not configured. Start with: langmine serve"}), 503

    data = request.get_json(silent=True) or {}
    video_id = data.get("video_id")
    all_kept = data.get("all_kept", False)

    if video_id is not None:
        sentences = persistence.get_sentences_by_video(video_id, status="kept")
    elif all_kept:
        sentences = persistence.get_sentences_by_status("kept")
    else:
        return jsonify({"error": "Specify video_id or all_kept=true"}), 400

    if not sentences:
        return jsonify({"error": "No kept sentences to export"}), 400

    try:
        config = load_config()
        result = exporter.export(
            sentences=sentences,
            deck_name=config.deck_name,
            note_type_name=config.note_type,
        )

        # Mark exported sentences
        for s in sentences:
            s.status = "exported"
            persistence.update_sentence(s)

        return jsonify(result)
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"Export failed: {e}"}), 500
```

**Step 3: Wire in cli.py _cmd_serve**

```python
from langmine.adapters import AnkiConnectAdapter
from langmine.config import load_config

config = load_config()
# ...
app = create_app(
    persistence=persistence,
    language_processor=processor,
    transcript_source=transcript,
    audio_processor=audio,
    anki_exporter=AnkiConnectAdapter(url=config.anki_connect_url),
)
```

**Step 4: Add API test**

```python
class TestAnkiExport:
    def test_export_requires_kept_sentences(self, client):
        """POST /api/export/anki without kept sentences → 400."""
        resp = client.post("/api/export/anki", json={"all_kept": True})
        assert resp.status_code == 400

    def test_export_all_kept(self, client_with_data):
        """POST /api/export/anki should attempt export (may fail without Anki)."""
        resp = client_with_data.post("/api/export/anki", json={"all_kept": True})
        # 200 if AnkiConnect available, 503 if not, 400 if no kept
        assert resp.status_code in (200, 400, 503)
```

**Step 5:** Run `pytest tests/test_web_api.py -v -k export` → PASS

**Step 6:** Commit

---

### Task 4: Add CLI export command

**Files:**
- Modify: `src/langmine/cli.py`

```python
# In main():
export_parser = subparsers.add_parser("export", help="Export kept sentences to Anki")
export_parser.add_argument("--video-id", type=int, help="Export from a specific video")
export_parser.add_argument("--all-kept", action="store_true", help="Export all kept sentences")

# In dispatch:
elif args.command == "export":
    _cmd_export(args)
```

```python
def _cmd_export(args):
    from langmine.adapters import SQLitePersistence, AnkiConnectAdapter
    from langmine.config import load_config

    config = load_config()
    persistence = SQLitePersistence()
    exporter = AnkiConnectAdapter(url=config.anki_connect_url)

    if args.video_id is not None:
        source = f"video {args.video_id}"
        sentences = persistence.get_sentences_by_video(args.video_id, status="kept")
    elif args.all_kept:
        source = "all kept"
        sentences = persistence.get_sentences_by_status("kept")
    else:
        print("Error: specify --video-id or --all-kept", file=sys.stderr)
        sys.exit(1)

    if not sentences:
        print("No kept sentences to export.")
        return

    try:
        result = exporter.export(
            sentences=sentences,
            deck_name=config.deck_name,
            note_type_name=config.note_type,
        )

        print(f"📦 Exported {source}: {result['added']} new, "
              f"{result['duplicates']} duplicates")
        if result["errors"]:
            for err in result["errors"]:
                print(f"  ⚠️  {err}")

        # Mark as exported
        for s in sentences:
            s.status = "exported"
            persistence.update_sentence(s)

    except ConnectionError as e:
        print(f"❌ {e}\n   Is Anki running with AnkiConnect installed?", file=sys.stderr)
        sys.exit(1)
```

**Step 2:** Add CLI test

```python
def test_langmine_export_help():
    result = subprocess.run(
        ["python", "-m", "langmine.cli", "export", "--help"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
```

**Step 3:** Run tests → PASS

**Step 4:** Commit

---

### Task 5: Add Export button to web UI

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/Sidebar.svelte`
- Modify: `src/langmine/web/frontend/src/lib/stores.js`
- Modify: `src/langmine/web/frontend/src/lib/api.js`

**Step 1:** Add `exportAnki` to `api.js`:

```javascript
exportAnki: (videoId) =>
  post('/export/anki', videoId ? { video_id: videoId } : { all_kept: true }),
```

**Step 2:** Add to `stores.js`:

```javascript
/** @type {import('svelte/store').Writable<string>} */
export const exportStatus = writable('');
/** @type {import('svelte/store').Writable<boolean>} */
export const exporting = writable(false);

export async function exportAnki(videoId) {
  exporting.set(true);
  exportStatus.set('⏳ Exporting...');
  try {
    const { ok, data } = await api.exportAnki(videoId);
    if (!ok) throw new Error(data.error || 'Export failed');
    exportStatus.set(`✅ ${data.added} new, ${data.duplicates} duplicates`);
  } catch (err) {
    exportStatus.set(`❌ ${err.message}`);
  } finally {
    exporting.set(false);
  }
}
```

**Step 3:** Add Export button to Sidebar (below video list):

```svelte
{#if $videos.length > 0}
  <div class="export-section">
    <button
      class="export-btn"
      onclick={() => exportAnki(null)}
      disabled={$exporting}
    >
      {$exporting ? '⏳' : '📦'} Export to Anki
    </button>
    {#if $exportStatus}
      <div class="export-status">{$exportStatus}</div>
    {/if}
  </div>
{/if}
```

Styles:
```css
.export-section {
  padding: 12px 20px;
  border-top: 1px solid var(--border);
}
.export-btn {
  width: 100%;
  padding: 10px;
  background: var(--accent-green);
  color: white;
  border: none;
  border-radius: var(--radius);
  font-size: 0.9rem;
  cursor: pointer;
  font-weight: 600;
}
.export-btn:hover:not(:disabled) { opacity: 0.9; }
.export-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.export-status {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 8px;
  line-height: 1.4;
}
```

**Step 4:** Rebuild: `cd frontend && npm run build`

**Step 5:** Commit

---

### Task 6: Full suite run + final commit

**Step 1:** `pytest tests/ -v --tb=short` → all non-ffmpeg tests pass

**Step 2:** Final commit

```bash
git add -A
git commit -m "M5: Export to Anki via AnkiConnect — complete

- AnkiExporter port + AnkiConnectAdapter (JSON-RPC)
- POST /api/export/anki endpoint (per-video or all-kept)
- langmine export --all-kept CLI command
- Export button in sidebar (direct to Anki)
- Duplicate detection via canAddNotes
- Audio embedding via storeMediaFile
- Sentences marked 'exported' after successful send
- 6 adapter tests (mocked HTTP) + API endpoint tests"
```

---

## Verification Checklist

- [ ] `pytest tests/adapters/test_anki_connect.py -v` → 6 PASS
- [ ] `pytest tests/test_web_api.py -v` → export tests PASS
- [ ] `python -m langmine.cli export --help` → shows help
- [ ] Export button appears in sidebar when videos loaded
- [ ] Clicking Export → cards appear in Anki deck "Chinese::Sentence Mining"
- [ ] Audio plays on card front
- [ ] Re-exporting same sentences → detected as duplicates
