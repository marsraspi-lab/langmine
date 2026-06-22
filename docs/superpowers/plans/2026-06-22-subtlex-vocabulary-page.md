# SUBTLEX-Powered Vocabulary Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vocab-table-only vocabulary page with a SUBTLEX-driven page showing all 99K words ordered by frequency, paginated 100/page, with client-cached word detail and anchored popover reclassification.

**Architecture:** New port methods (`list_words`, `get_sentences_by_words`, `update_vocab_status`, `get_vocab_statuses`, `get_words_by_status`, `get_classified_words`) implemented in existing adapters. New `GET /api/vocab/subtlex` endpoint returns full word detail including definitions and sentences — popover reads from client page cache. PATCH endpoint fixed to upsert. `FrequencySource` and `Dictionary` ports wired into Flask app config.

**Tech Stack:** Python 3.11+ (Flask, SQLite), Svelte 5 (runes), Playwright for E2E tests.

---

### Task 1: Add `list_words()` and `count_words()` to FrequencySource port + adapters

**Files:**
- Modify: `src/langmine/domain/ports.py:357-367`
- Modify: `src/langmine/languages/chinese/frequency.py`
- Modify: `src/langmine/languages/chinese/jieba_frequency.py`
- Create: `tests/test_frequency.py` (or extend existing)

- [ ] **Step 1: Add abstract methods to FrequencySource ABC**

In `src/langmine/domain/ports.py`, in the `FrequencySource` class, add after `get_frequency`:

```python
@abstractmethod
def list_words(
    self, offset: int = 0, limit: int = 100
) -> list[tuple[str, int]]:
    """Return a slice of words ordered by frequency rank.
    Returns list of (word_simplified, frequency_rank) tuples.
    offset=0 returns the most frequent words first.
    """
    ...

@abstractmethod
def count_words(self) -> int:
    """Return total number of words in the frequency list."""
    ...
```

- [ ] **Step 2: Implement in SubtlexChAdapter**

In `src/langmine/languages/chinese/frequency.py`, in `__init__`, add `self._ordered_words: list[str] = []` before `self._load()`.

In `_load()`, after the existing line that builds `self._rank`, add:
```python
self._ordered_words = [word for word, _ in entries]
```

After `get_frequency()`, add:
```python
def list_words(
    self, offset: int = 0, limit: int = 100
) -> list[tuple[str, int]]:
    end = min(offset + limit, len(self._ordered_words))
    return [
        (word, self._rank[word])
        for word in self._ordered_words[offset:end]
    ]

def count_words(self) -> int:
    return len(self._ordered_words)
```

- [ ] **Step 3: Implement stubs in JiebaFrequencyAdapter**

In `src/langmine/languages/chinese/jieba_frequency.py`, after `get_frequency()`:

```python
def list_words(
    self, offset: int = 0, limit: int = 100
) -> list[tuple[str, int]]:
    end = min(offset + limit, len(self._rank))
    return sorted(
        self._rank.items(), key=lambda x: x[1]
    )[offset:end]

def count_words(self) -> int:
    return len(self._rank)
```

- [ ] **Step 4: Write tests in `tests/test_frequency.py`**

```python
from langmine.languages.chinese.frequency import SubtlexChAdapter


def test_subtlex_list_words_first_page():
    adapter = SubtlexChAdapter()
    words = adapter.list_words(offset=0, limit=100)
    assert len(words) == 100
    assert words[0] == ("的", 1)
    assert words[1][1] == 2
    assert words[99][1] == 100


def test_subtlex_list_words_middle_page():
    adapter = SubtlexChAdapter()
    words = adapter.list_words(offset=100, limit=100)
    assert len(words) == 100
    assert words[0][1] == 101
    assert words[99][1] == 200


def test_subtlex_list_words_last_page_partial():
    adapter = SubtlexChAdapter()
    total = adapter.count_words()
    words = adapter.list_words(offset=total - 10, limit=100)
    assert len(words) == 10


def test_subtlex_count_words():
    adapter = SubtlexChAdapter()
    assert adapter.count_words() == 99124


def test_subtlex_list_words_returns_tuples():
    adapter = SubtlexChAdapter()
    words = adapter.list_words(offset=0, limit=5)
    for w in words:
        assert isinstance(w, tuple)
        assert len(w) == 2
        assert isinstance(w[0], str)
        assert isinstance(w[1], int)
```

- [ ] **Step 5: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_frequency.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/langmine/domain/ports.py src/langmine/languages/chinese/frequency.py src/langmine/languages/chinese/jieba_frequency.py tests/test_frequency.py
git commit -m "feat: add list_words() and count_words() to FrequencySource port"
```

---

### Task 2: Add `get_sentences_by_words()` to SentenceRepository port + SQLite adapter

**Files:**
- Modify: `src/langmine/domain/ports.py` (SentenceRepository class)
- Modify: `src/langmine/adapters/sqlite_persistence.py`
- Modify: `tests/test_web_api.py` (FakePersistence)

- [ ] **Step 1: Add abstract method to SentenceRepository ABC**

In `src/langmine/domain/ports.py`, in `SentenceRepository`, after `get_sentences_by_word`:

```python
@abstractmethod
def get_sentences_by_words(
    self, words: list[str], max_per_word: int = 5
) -> dict[str, list[Sentence]]:
    """Return sentences for multiple words, capped per word.
    Words with no sentences return empty lists.
    """
    ...
```

- [ ] **Step 2: Implement in SQLitePersistence**

In `src/langmine/adapters/sqlite_persistence.py`, after `get_sentences_by_word`:

```python
def get_sentences_by_words(
    self, words: list[str], max_per_word: int = 5
) -> dict[str, list[Sentence]]:
    if not words:
        return {}
    placeholders = ", ".join(["?"] * len(words))
    query = f"""
        SELECT * FROM (
            SELECT *,
                row_number() OVER (
                    PARTITION BY unknown_word ORDER BY id DESC
                ) AS rn
            FROM sentences
            WHERE unknown_word IN ({placeholders})
        ) WHERE rn <= ?
    """
    rows = self.conn.execute(
        query, (*words, max_per_word)
    ).fetchall()
    result: dict[str, list[Sentence]] = {w: [] for w in words}
    for row in rows:
        s = self._row_to_sentence(row)
        w = s.unknown_word
        if w and w in result:
            result[w].append(s)
    return result
```

- [ ] **Step 3: Add stub to FakePersistence**

In the `FakePersistence` class in `tests/test_web_api.py`:

```python
def get_sentences_by_words(self, words, max_per_word=5):
    result = {w: [] for w in words}
    for w in words:
        result[w] = self._sentences.get(w, [])[:max_per_word]
    return result
```

(Adjust `self._sentences` to match whatever internal structure FakePersistence uses for sentence storage.)

- [ ] **Step 4: Write test for SQLite implementation**

In `tests/test_sqlite_persistence.py`:

```python
def test_get_sentences_by_words_caps_per_word():
    from langmine.domain.models import Sentence
    p = SQLitePersistence(":memory:")
    for i in range(10):
        p.save_sentences([Sentence(
            video_id=1, start_ms=0, end_ms=100,
            text=f"的text{i}", unknown_word="的", status="new"
        )])
    for i in range(3):
        p.save_sentences([Sentence(
            video_id=1, start_ms=0, end_ms=100,
            text=f"我text{i}", unknown_word="我", status="new"
        )])
    result = p.get_sentences_by_words(["的", "我", "吗"], max_per_word=5)
    assert len(result["的"]) == 5
    assert len(result["我"]) == 3
    assert len(result["吗"]) == 0
```

- [ ] **Step 5: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/ -v -k "sentences_by_words"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/langmine/domain/ports.py src/langmine/adapters/sqlite_persistence.py tests/
git commit -m "feat: add get_sentences_by_words() to SentenceRepository port"
```

---

### Task 3: Add `update_vocab_status()` to VocabRepository port + adapter

**Files:**
- Modify: `src/langmine/domain/ports.py` (VocabRepository class)
- Modify: `src/langmine/adapters/sqlite_persistence.py`
- Modify: `tests/test_web_api.py` (FakePersistence)

- [ ] **Step 1: Add abstract method to VocabRepository ABC**

In `src/langmine/domain/ports.py`, in `VocabRepository`, add after `mark_word_ignored`:

```python
@abstractmethod
def update_vocab_status(
    self, word_simplified: str, status: str, language_code: str = ""
) -> None:
    """Upsert a word's status: INSERT if new, UPDATE only status if exists.
    Never overwrites reading, definition, hsk_level, or frequency_rank
    on existing rows.
    """
    ...
```

- [ ] **Step 2: Implement in SQLitePersistence**

In `src/langmine/adapters/sqlite_persistence.py`, after `mark_word_ignored`:

```python
def update_vocab_status(
    self, word_simplified: str, status: str, language_code: str = ""
) -> None:
    now = datetime.now(UTC).isoformat()
    lang = language_code or "zh"
    self.conn.execute(
        """INSERT INTO vocab (word_simplified, status, language_code,
           created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(word_simplified) DO UPDATE SET
               status = excluded.status,
               updated_at = excluded.updated_at""",
        (word_simplified, status, lang, now, now),
    )
    self.conn.commit()
```

- [ ] **Step 3: Add stub to FakePersistence**

```python
def update_vocab_status(self, word_simplified, status, language_code=""):
    if word_simplified in self._vocab:
        self._vocab[word_simplified].status = status
    else:
        from langmine.domain.models import VocabWord
        self._vocab[word_simplified] = VocabWord(
            word_simplified=word_simplified,
            status=status,
            language_code=language_code or "zh",
        )
```

- [ ] **Step 4: Write tests**

```python
def test_update_vocab_status_upserts_new_word():
    p = SQLitePersistence(":memory:")
    p.update_vocab_status("测试", "learning", "zh")
    word = p.get_vocab_word("测试")
    assert word is not None
    assert word.status == "learning"


def test_update_vocab_status_preserves_existing_fields():
    from langmine.domain.models import VocabWord
    p = SQLitePersistence(":memory:")
    p.save_vocab_word(VocabWord(
        word_simplified="的", reading="de",
        definition_de="Partikel", hsk_level=1,
        frequency_rank=1, status="known", language_code="zh",
    ))
    p.update_vocab_status("的", "ignored", "zh")
    word = p.get_vocab_word("的")
    assert word.status == "ignored"
    assert word.reading == "de"
    assert word.definition_de == "Partikel"
    assert word.hsk_level == 1
    assert word.frequency_rank == 1
```

- [ ] **Step 5: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/ -v -k "update_vocab_status"
```

Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/langmine/domain/ports.py src/langmine/adapters/sqlite_persistence.py tests/
git commit -m "feat: add update_vocab_status() to VocabRepository port"
```

---

### Task 4: Add batch lookup port methods + schema migration

**Files:**
- Modify: `src/langmine/domain/ports.py` (VocabRepository class)
- Modify: `src/langmine/adapters/sqlite_persistence.py`
- Modify: `src/langmine/db.py`
- Modify: `tests/test_web_api.py` (FakePersistence)

- [ ] **Step 1: Add `get_vocab_statuses`, `get_words_by_status`, `get_classified_words` to VocabRepository ABC**

In `src/langmine/domain/ports.py`, in `VocabRepository`:

```python
@abstractmethod
def get_vocab_statuses(
    self, words: list[str], language_code: str = ""
) -> dict[str, str]:
    """Batch-lookup status for a list of words.
    Returns dict mapping word_simplified -> status.
    Words not in the table are absent from the dict.
    """
    ...

@abstractmethod
def get_words_by_status(
    self, status: str, language_code: str = ""
) -> set[str]:
    """Return all word_simplified with a given status."""
    ...

@abstractmethod
def get_classified_words(
    self, language_code: str = ""
) -> set[str]:
    """Return all word_simplified with any classified status
    (known, learning, ignored, proper-name)."""
    ...
```

- [ ] **Step 2: Implement in SQLitePersistence**

In `src/langmine/adapters/sqlite_persistence.py`:

```python
def get_vocab_statuses(
    self, words: list[str], language_code: str = ""
) -> dict[str, str]:
    if not words:
        return {}
    placeholders = ", ".join(["?"] * len(words))
    rows = self.conn.execute(
        f"SELECT word_simplified, status FROM vocab"
        f" WHERE word_simplified IN ({placeholders})",
        words,
    ).fetchall()
    return {row["word_simplified"]: row["status"] for row in rows}


def get_words_by_status(
    self, status: str, language_code: str = ""
) -> set[str]:
    suffix, params = self._lang_filter(language_code)
    rows = self.conn.execute(
        f"SELECT word_simplified FROM vocab"
        f" WHERE status = ?{suffix}",
        (status, *params),
    ).fetchall()
    return {row["word_simplified"] for row in rows}


def get_classified_words(
    self, language_code: str = ""
) -> set[str]:
    suffix, params = self._lang_filter(language_code)
    rows = self.conn.execute(
        f"SELECT word_simplified FROM vocab"
        f" WHERE status IN ('known','learning','ignored','proper-name'){suffix}",
        params,
    ).fetchall()
    return {row["word_simplified"] for row in rows}
```

- [ ] **Step 3: Add stubs to FakePersistence**

```python
def get_vocab_statuses(self, words, language_code=""):
    result = {}
    for w in words:
        vw = self._vocab.get(w)
        if vw:
            result[w] = vw.status
    return result

def get_words_by_status(self, status, language_code=""):
    return {
        w for w, v in self._vocab.items()
        if v.status == status
        and (not language_code or v.language_code == language_code)
    }

def get_classified_words(self, language_code=""):
    return {
        w for w, v in self._vocab.items()
        if v.status in ("known", "learning", "ignored", "proper-name")
        and (not language_code or v.language_code == language_code)
    }
```

- [ ] **Step 4: Schema migration v8→v9**

In `src/langmine/db.py`, change `SCHEMA_VERSION = 8` to `SCHEMA_VERSION = 9`.

In `_ensure_schema()`, after the v8 migration block, add:

```python
if current < 9:
    self.conn.execute(
        "DELETE FROM vocab WHERE id NOT IN"
        " (SELECT MIN(id) FROM vocab GROUP BY word_simplified)"
    )
    try:
        self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_vocab_word"
            " ON vocab(word_simplified)"
        )
    except sqlite3.OperationalError:
        pass
    try:
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sentences_unknown_word"
            " ON sentences(unknown_word)"
        )
    except sqlite3.OperationalError:
        pass
    self.conn.commit()
```

- [ ] **Step 5: Extend get_vocab_stats() to return ignored and proper_name**

In `src/langmine/adapters/sqlite_persistence.py`, in `get_vocab_stats()`, add after the learning count:

```python
ignored = self.conn.execute(
    f"SELECT COUNT(*) FROM vocab WHERE status = 'ignored'{suffix}", params
).fetchone()[0]
proper_name = self.conn.execute(
    f"SELECT COUNT(*) FROM vocab WHERE status = 'proper-name'{suffix}",
    params,
).fetchone()[0]
```

And change the return to include `"ignored": ignored, "proper_name": proper_name`.

Update FakePersistence's `get_vocab_stats()` to also return `ignored` and `proper_name`.

- [ ] **Step 6: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_web_api.py -v
```

Expected: All existing tests PASS with updated FakePersistence.

- [ ] **Step 7: Commit**

```bash
git add src/langmine/domain/ports.py src/langmine/adapters/sqlite_persistence.py src/langmine/db.py tests/
git commit -m "feat: add batch vocab lookup methods, schema v9, get_vocab_stats fix"
```

---

### Task 5: Wiring — inject FrequencySource and Dictionary into Flask config

**Files:**
- Modify: `src/langmine/web/app.py`
- Modify: `src/langmine/web/routes/_helpers.py`
- Modify: `tests/test_web_api.py` (all `client()` fixtures)

- [ ] **Step 1: Add params to create_app()**

In `src/langmine/web/app.py`, add imports at top:
```python
from langmine.domain.ports import FrequencySource, Dictionary
```

Change `create_app` signature to add two new optional params after `image_searcher`:
```python
frequency_source: FrequencySource | None = None,
dictionary: Dictionary | None = None,
```

Inside `create_app`, after the `LANGMINE_IMAGE_SEARCHER` line, add:
```python
app.config["LANGMINE_FREQUENCY_SOURCE"] = frequency_source
app.config["LANGMINE_DICTIONARY"] = dictionary
```

- [ ] **Step 2: Add accessors in _helpers.py**

In `src/langmine/web/routes/_helpers.py`, after `_get_persistence()`:

```python
def _get_frequency_source():
    """Get the frequency source port from app config."""
    return current_app.config.get("LANGMINE_FREQUENCY_SOURCE")


def _get_dictionary():
    """Get the dictionary port from app config."""
    return current_app.config.get("LANGMINE_DICTIONARY")
```

- [ ] **Step 3: Wire in create_production_app()**

In `src/langmine/web/app.py`, in `create_production_app()`, the `create_language_adapters()` call already returns `(dictionary, frequency)`. Pass them to the `create_app()` call at the end:

```python
return create_app(
    persistence=persistence,
    language_processor=processor,
    transcript_source=transcript,
    audio_processor=audio,
    anki_exporter=AnkiConnectAdapter(url=config.anki_connect_url),
    image_searcher=image_searcher,
    frequency_source=frequency,
    dictionary=dictionary,
    config=config,
)
```

- [ ] **Step 4: Update all test client() fixtures**

In every test file with a `client()` fixture, add `frequency_source=None, dictionary=None` to every `create_app()` call.

- [ ] **Step 5: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_web_api.py -v
```

Expected: All existing tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/langmine/web/app.py src/langmine/web/routes/_helpers.py tests/
git commit -m "feat: inject FrequencySource and Dictionary into Flask config"
```

---

### Task 6: Fix PATCH /api/vocab/<word> — upsert via update_vocab_status

**Files:**
- Modify: `src/langmine/web/routes/vocab.py`

- [ ] **Step 1: Rewrite the three helper functions**

In `src/langmine/web/routes/vocab.py`, replace `_apply_word_status`, `_mark_proper_name`, and `_dismiss_proper_name`:

```python
def _apply_word_status(persistence, word, lang, new_status):
    """Apply a word status change, upserting the word if needed."""
    persistence.update_vocab_status(word, new_status, lang)
    persistence.log_event(
        entity_type="word", entity_id=0,
        action=f"marked_{new_status}",
        new_value=word, language_code=lang,
    )


def _mark_proper_name(persistence, word, lang):
    """Mark a word as a proper name."""
    existing = persistence.get_vocab_word(word)
    persistence.update_vocab_status(word, "proper-name", lang)
    persistence.log_event(
        entity_type="word", entity_id=0,
        action="marked_proper_name",
        old_value=existing.status if existing else "unknown",
        new_value="proper-name", language_code=lang,
    )


def _dismiss_proper_name(persistence, word, lang):
    """Dismiss a proper-name classification."""
    persistence.update_vocab_status(word, "learning", lang)
    persistence.log_event(
        entity_type="word", entity_id=0,
        action="dismissed_proper_name",
        old_value="proper-name",
        new_value="learning", language_code=lang,
    )
```

- [ ] **Step 2: Update the route to return full word object**

In `update_vocab_word()`, change each return to include the full word:

```python
word_obj = persistence.get_vocab_word(word)
return jsonify({"word": _vocab_to_dict(word_obj, persistence), "ok": True})
```

- [ ] **Step 3: Write tests**

```python
def test_patch_vocab_upserts_new_word(client):
    resp = client.patch("/api/vocab/测试", json={"status": "known"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["word"]["word"] == "测试"
    assert data["word"]["status"] == "known"


def test_patch_vocab_preserves_fields(client):
    # First create
    client.patch("/api/vocab/的", json={"status": "known"})
    # Then update
    resp = client.patch("/api/vocab/的", json={"status": "learning"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["word"]["status"] == "learning"
    assert data["word"]["word"] == "的"
```

- [ ] **Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_web_api.py -v -k "patch_vocab"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/langmine/web/routes/vocab.py tests/
git commit -m "fix: PATCH /api/vocab/<word> upserts via update_vocab_status, returns full word"
```

---

### Task 7: New GET /api/vocab/subtlex endpoint

**Files:**
- Modify: `src/langmine/web/routes/vocab.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Add the endpoint**

In `src/langmine/web/routes/vocab.py`, after the `list_vocab` route:

```python
@vocab_bp.route("/api/vocab/subtlex", methods=["GET"])
def list_subtlex_vocab():
    """Return a page of SUBTLEX words enriched with vocab status,
    dictionary definitions, and example sentences."""
    persistence = _get_persistence()
    frequency_source = _get_frequency_source()
    dictionary = _get_dictionary()
    lang = _get_language_code()

    if not frequency_source:
        return jsonify({"error": "Frequency source not configured"}), 501

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 100, type=int), 500)
    status_filter = request.args.get("status", None, type=str)
    search = request.args.get("search", None, type=str)

    if page < 1:
        return jsonify({"error": "page must be >= 1"}), 400
    if per_page < 1:
        return jsonify({"error": "per_page must be >= 1"}), 400
    valid_statuses = {"known", "learning", "ignored", "unknown"}
    if status_filter and status_filter not in valid_statuses:
        return jsonify(
            {"error": f"status must be one of {sorted(valid_statuses)}"}
        ), 400

    total_subtlex = frequency_source.count_words()
    all_words = frequency_source.list_words(0, total_subtlex)

    # Filter
    if status_filter:
        if status_filter == "unknown":
            classified = persistence.get_classified_words(lang)
            matching = [(w, r) for w, r in all_words if w not in classified]
        else:
            words_set = persistence.get_words_by_status(status_filter, lang)
            matching = [(w, r) for w, r in all_words if w in words_set]
    elif search:
        matching = [(w, r) for w, r in all_words if search in w]
    else:
        matching = all_words

    # Paginate
    total = len(matching)
    offset = (page - 1) * per_page
    page_words = matching[offset : offset + per_page]

    words_only = [w for w, _ in page_words]
    vocab_statuses = persistence.get_vocab_statuses(words_only, lang)
    sentences_map = persistence.get_sentences_by_words(words_only, max_per_word=5)

    from langmine.domain.models import frequency_badge

    enriched = []
    for word_simplified, rank in page_words:
        status = vocab_statuses.get(word_simplified, "unknown")
        dict_entry = dictionary.lookup(word_simplified) if dictionary else None
        reading = dict_entry.get("pinyin", "") if dict_entry else ""
        definition_de = dict_entry.get("definition_de", "") if dict_entry else ""
        definition_en = dict_entry.get("definition_en", "") if dict_entry else ""
        hsk_level = None
        try:
            from langmine.language_factory import get_proficiency_level
            hsk_level = get_proficiency_level(word_simplified, lang)
        except Exception:
            pass
        raw = sentences_map.get(word_simplified, [])
        enriched.append({
            "word_simplified": word_simplified,
            "word_traditional": "",
            "reading": reading,
            "definition_de": definition_de,
            "definition_en": definition_en,
            "frequency_rank": rank,
            "frequency_badge": frequency_badge(rank),
            "hsk_level": hsk_level,
            "status": status,
            "sentence_count": len(raw),
            "sentences": [
                {
                    "id": s.id,
                    "text": s.text,
                    "reading": s.reading or "",
                    "translation": s.translation or "",
                }
                for s in raw
            ],
        })

    stats = persistence.get_vocab_stats(lang)
    known_count = stats.get("known", 0)
    learning_count = stats.get("learning", 0)
    ignored_count = stats.get("ignored", 0)
    proper_name_count = stats.get("proper_name", 0)
    unknown_count = (
        total_subtlex
        - known_count - learning_count - ignored_count - proper_name_count
    )

    return jsonify({
        "words": enriched,
        "total": total,
        "page": page,
        "per_page": per_page,
        "counts": {
            "all": total_subtlex,
            "known": known_count,
            "learning": learning_count,
            "ignored": ignored_count,
            "unknown": max(unknown_count, 0),
        },
    })
```

- [ ] **Step 2: Write tests**

```python
def test_subtlex_endpoint_returns_first_page(client):
    resp = client.get("/api/vocab/subtlex?page=1&per_page=100")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["words"]) == 100
    assert data["words"][0]["word_simplified"] == "的"
    assert data["words"][0]["frequency_rank"] == 1
    assert data["words"][0]["status"] == "unknown"
    assert "sentences" in data["words"][0]
    assert "counts" in data


def test_subtlex_endpoint_pagination(client):
    resp = client.get("/api/vocab/subtlex?page=2&per_page=100")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["page"] == 2
    assert data["words"][0]["frequency_rank"] == 101


def test_subtlex_endpoint_respects_per_page(client):
    resp = client.get("/api/vocab/subtlex?per_page=50")
    assert resp.status_code == 200
    assert len(resp.get_json()["words"]) == 50


def test_subtlex_endpoint_rejects_invalid_status(client):
    resp = client.get("/api/vocab/subtlex?status=invalid")
    assert resp.status_code == 400


def test_subtlex_endpoint_rejects_invalid_page(client):
    resp = client.get("/api/vocab/subtlex?page=0")
    assert resp.status_code == 400


def test_subtlex_endpoint_filters_by_status(client):
    # Mark one word as known
    client.patch("/api/vocab/的", json={"status": "known"})
    resp = client.get("/api/vocab/subtlex?status=known&per_page=10")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(w["word_simplified"] == "的" for w in data["words"])


def test_subtlex_endpoint_unknown_filter_excludes_classified(client):
    client.patch("/api/vocab/的", json={"status": "known"})
    resp = client.get("/api/vocab/subtlex?status=unknown&per_page=100")
    assert resp.status_code == 200
    data = resp.get_json()
    words_in_page = {w["word_simplified"] for w in data["words"]}
    assert "的" not in words_in_page


def test_subtlex_endpoint_counts_match(client):
    client.patch("/api/vocab/的", json={"status": "known"})
    resp = client.get("/api/vocab/subtlex?per_page=5")
    data = resp.get_json()
    counts = data["counts"]
    assert counts["known"] >= 1
    assert counts["all"] > 0
```

- [ ] **Step 3: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_web_api.py -v -k "subtlex"
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/langmine/web/routes/vocab.py tests/
git commit -m "feat: add GET /api/vocab/subtlex endpoint with counts and filtered views"
```

---

### Task 8: Frontend — api.js and WordPopover.svelte

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/api.js`
- Create: `src/langmine/web/frontend/src/lib/WordPopover.svelte`

- [ ] **Step 1: Add fetchSubtlexVocab() to api.js**

In `src/langmine/web/frontend/src/lib/api.js`, after `fetchVocab`:

```js
export async function fetchSubtlexVocab(page = 1, perPage = 100, status = null, search = null) {
    const params = new URLSearchParams({ page, per_page: perPage });
    if (status) params.set('status', status);
    if (search) params.set('search', search);
    const res = await fetch(`/api/vocab/subtlex?${params}`);
    return res.json();
}
```

- [ ] **Step 2: Create WordPopover.svelte**

Create `src/langmine/web/frontend/src/lib/WordPopover.svelte`:

```svelte
<script>
    import { markWordStatus } from './stores.svelte.js';

    let { word, onclose } = $props();

    function handleStatusChange(newStatus) {
        markWordStatus(word.word_simplified, newStatus);
        if (onclose) onclose();
    }

    const statusLabel = $derived({
        known: 'Known',
        learning: 'Learning',
        ignored: 'Ignored',
        unknown: 'Unknown',
        'proper-name': 'Proper name',
    }[word.status] || word.status);

    const statusColor = $derived({
        known: 'var(--green, #2ecc71)',
        learning: 'var(--orange, #e67e22)',
        ignored: 'var(--gray, #95a5a6)',
        unknown: 'var(--red, #e74c3c)',
        'proper-name': 'var(--gray, #95a5a6)',
    }[word.status] || 'inherit');

    function handleKeydown(e) {
        if (e.key === 'Escape') onclose?.();
    }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Overlay -->
<button class="popover-overlay" onclick={onclose}></button>

<div class="word-popover">
    <button class="close-btn" onclick={onclose}>✕</button>

    <div class="word-header">
        <span class="word-text">{word.word_simplified}</span>
        {#if word.reading}
            <span class="word-reading">{word.reading}</span>
        {/if}
    </div>

    <div class="word-badges">
        {#if word.frequency_badge}
            <span class="badge freq">🔥 #{word.frequency_rank}</span>
        {/if}
        {#if word.hsk_level}
            <span class="badge hsk">HSK {word.hsk_level}</span>
        {/if}
    </div>

    <div class="word-definitions">
        {#if word.definition_de}
            <div class="def">DE: {word.definition_de}</div>
        {/if}
        {#if word.definition_en}
            <div class="def">EN: {word.definition_en}</div>
        {/if}
    </div>

    <div class="word-status">
        Status: <span style="color: {statusColor}">● {statusLabel}</span>
    </div>

    <div class="status-actions">
        {#each ['known', 'learning', 'ignored'] as s}
            <button
                class="status-btn"
                disabled={word.status === s}
                onclick={() => handleStatusChange(s)}
            >
                Mark {s}
            </button>
        {/each}
    </div>

    <div class="sentences-section">
        <div class="sentences-title">Example sentences ({word.sentences?.length || 0}):</div>
        {#if word.sentences?.length}
            {#each word.sentences as s}
                <div class="sentence-item">
                    <div class="sentence-text">{s.text}</div>
                    {#if s.reading}
                        <div class="sentence-reading">{s.reading}</div>
                    {/if}
                    {#if s.translation}
                        <div class="sentence-translation">{s.translation}</div>
                    {/if}
                </div>
            {/each}
        {:else}
            <div class="no-sentences">No example sentences yet</div>
        {/if}
    </div>
</div>

<style>
    .popover-overlay {
        position: fixed;
        inset: 0;
        z-index: 90;
        background: transparent;
        border: none;
        cursor: default;
    }
    .word-popover {
        position: fixed;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
        z-index: 100;
        background: var(--bg-card, #1e1e2e);
        border: 1px solid var(--border, #333);
        border-radius: 10px;
        padding: 20px 24px;
        min-width: 320px;
        max-width: 420px;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
    }
    .close-btn {
        position: absolute;
        top: 10px;
        right: 14px;
        background: none;
        border: none;
        color: var(--text-muted, #888);
        font-size: 18px;
        cursor: pointer;
        padding: 4px 8px;
    }
    .close-btn:hover { color: var(--text, #eee); }
    .word-header {
        display: flex;
        align-items: baseline;
        gap: 10px;
        margin-bottom: 8px;
    }
    .word-text {
        font-size: 28px;
        font-weight: 600;
        color: var(--text, #eee);
    }
    .word-reading {
        font-size: 16px;
        color: var(--text-muted, #aaa);
    }
    .word-badges {
        display: flex;
        gap: 8px;
        margin-bottom: 12px;
    }
    .badge {
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 4px;
        background: var(--bg-accent, #2a2a3e);
    }
    .word-definitions {
        margin-bottom: 12px;
    }
    .def {
        font-size: 14px;
        color: var(--text-muted, #bbb);
        line-height: 1.5;
    }
    .word-status {
        font-size: 14px;
        margin-bottom: 12px;
        color: var(--text-muted, #bbb);
    }
    .status-actions {
        display: flex;
        gap: 6px;
        margin-bottom: 16px;
    }
    .status-btn {
        flex: 1;
        padding: 6px 10px;
        font-size: 13px;
        border: 1px solid var(--border, #444);
        border-radius: 6px;
        background: var(--bg-card, #1e1e2e);
        color: var(--text, #eee);
        cursor: pointer;
    }
    .status-btn:hover:not(:disabled) {
        background: var(--bg-accent, #2a2a3e);
    }
    .status-btn:disabled {
        opacity: 0.4;
        cursor: default;
    }
    .sentences-title {
        font-size: 13px;
        color: var(--text-muted, #888);
        margin-bottom: 8px;
    }
    .sentence-item {
        background: var(--bg-accent, #252535);
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 8px;
    }
    .sentence-text {
        font-size: 16px;
        color: var(--text, #eee);
    }
    .sentence-reading {
        font-size: 13px;
        color: var(--text-muted, #aaa);
        margin-top: 2px;
    }
    .sentence-translation {
        font-size: 13px;
        color: var(--text-muted, #999);
        margin-top: 2px;
    }
    .no-sentences {
        font-size: 13px;
        color: var(--text-muted, #666);
        font-style: italic;
    }
</style>
```

- [ ] **Step 3: Build frontend to verify compilation**

```bash
cd src/langmine/web/frontend && npm run build && cd -
```

Expected: No build errors.

- [ ] **Step 4: Commit**

```bash
git add src/langmine/web/frontend/src/lib/api.js src/langmine/web/frontend/src/lib/WordPopover.svelte
git commit -m "feat: add fetchSubtlexVocab() and WordPopover component"
```

---

### Task 9: Frontend — Rewrite VocabPage.svelte

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/VocabPage.svelte`

- [ ] **Step 1: Replace VocabPage with SUBTLEX-driven version**

This is a full rewrite of `VocabPage.svelte`. The new version:

```svelte
<script>
    import { fetchSubtlexVocab } from './api.js';
    import WordPopover from './WordPopover.svelte';

    let words = $state([]);
    let total = $state(0);
    let page = $state(1);
    let perPage = $state(100);
    let statusFilter = $state(null);
    let searchQuery = $state('');
    let counts = $state({ all: 0, known: 0, learning: 0, ignored: 0, unknown: 0 });
    let loading = $state(false);
    let error = $state(null);
    let selectedWord = $state(null);

    // Debounce search
    let searchTimer = null;

    async function loadWords() {
        loading = true;
        error = null;
        try {
            const data = await fetchSubtlexVocab(
                page, perPage,
                statusFilter,
                searchQuery || null
            );
            words = data.words;
            total = data.total;
            counts = data.counts;
        } catch (err) {
            error = err.message;
            words = [];
        } finally {
            loading = false;
        }
    }

    function handleSearchInput(e) {
        searchQuery = e.target.value;
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            page = 1;
            loadWords();
        }, 300);
    }

    function goToPage(p) {
        if (p < 1 || p > totalPages || p === page) return;
        page = p;
        selectedWord = null;
        loadWords();
    }

    function setFilter(f) {
        if (statusFilter === f) return;
        statusFilter = f;
        page = 1;
        selectedWord = null;
        loadWords();
    }

    function handlePageKeydown(e) {
        if (e.key === 'Enter') {
            const p = parseInt(e.target.value);
            if (p >= 1) goToPage(p);
        }
    }

    // Load on mount
    $effect(() => { loadWords(); });

    let totalPages = $derived(Math.ceil(total / perPage));

    const statuses = [
        { key: null, label: 'All', countKey: 'all' },
        { key: 'known', label: 'Known', countKey: 'known' },
        { key: 'learning', label: 'Learning', countKey: 'learning' },
        { key: 'ignored', label: 'Ignored', countKey: 'ignored' },
        { key: 'unknown', label: 'Unknown', countKey: 'unknown' },
    ];

    function statusClass(s) {
        return { known: 's-known', learning: 's-learning', ignored: 's-ignored', unknown: 's-unknown' }[s] || '';
    }

    function openPopover(word) {
        selectedWord = word;
    }

    function closePopover() {
        selectedWord = null;
    }

    function handleReclassified() {
        // If the word no longer matches the filter, splice it out
        if (statusFilter && selectedWord) {
            if (selectedWord.status !== statusFilter) {
                const idx = words.findIndex(w => w.word_simplified === selectedWord.word_simplified);
                if (idx >= 0) {
                    // Update local counts
                    const oldStatus = statusFilter;
                    const newStatus = selectedWord.status;
                    counts = {
                        ...counts,
                        [oldStatus]: counts[oldStatus] - 1,
                        [newStatus]: (counts[newStatus] || 0) + 1,
                    };
                    words.splice(idx, 1);
                }
            }
        }
        closePopover();
    }
</script>

<div class="vocab-page">
    <!-- Filter tabs -->
    <div class="filter-tabs">
        {#each statuses as st}
            <button
                class="filter-tab"
                class:active={statusFilter === st.key}
                onclick={() => setFilter(st.key)}
            >
                {st.label} {counts[st.countKey]?.toLocaleString()}
            </button>
        {/each}
    </div>

    <!-- Search -->
    <div class="search-bar">
        <input
            type="text"
            placeholder="Search words..."
            value={searchQuery}
            oninput={handleSearchInput}
        />
    </div>

    <!-- Content -->
    {#if loading}
        <div class="loading">Loading...</div>
    {:else if error}
        <div class="error">
            {error}
            <button onclick={loadWords}>Retry</button>
        </div>
    {:else if words.length === 0}
        <div class="empty">No words found</div>
    {:else}
        <div class="word-list">
            <div class="list-header">
                <span class="col-rank">#</span>
                <span class="col-word">Word</span>
                <span class="col-reading">Reading</span>
                <span class="col-freq">Freq</span>
                <span class="col-status">Status</span>
            </div>
            {#each words as word, idx (word.word_simplified)}
                <button
                    class="word-row"
                    onclick={() => openPopover(word)}
                >
                    <span class="col-rank">{word.frequency_rank}</span>
                    <span class="col-word">{word.word_simplified}</span>
                    <span class="col-reading">{word.reading}</span>
                    <span class="col-freq">{word.frequency_badge}#{word.frequency_rank}</span>
                    <span class="col-status {statusClass(word.status)}">● {word.status}</span>
                </button>
            {/each}
        </div>

        <!-- Pagination -->
        <div class="pagination">
            <button onclick={() => goToPage(1)} disabled={page === 1}>◀◀ First</button>
            <button onclick={() => goToPage(page - 1)} disabled={page === 1}>◀ Prev</button>
            <span class="page-info">
                Page
                <input
                    type="number"
                    class="page-input"
                    value={page}
                    min="1"
                    max={totalPages}
                    onkeydown={handlePageKeydown}
                />
                of {totalPages.toLocaleString()}
            </span>
            <button onclick={() => goToPage(page + 1)} disabled={page === totalPages}>Next ▶</button>
            <button onclick={() => goToPage(totalPages)} disabled={page === totalPages}>Last ▶▶</button>
        </div>
    {/if}
</div>

<!-- Popover -->
{#if selectedWord}
    <WordPopover
        word={selectedWord}
        onclose={handleReclassified}
    />
{/if}

<style>
    .vocab-page {
        padding: 20px;
        max-width: 900px;
        margin: 0 auto;
        color: var(--text, #eee);
    }
    .filter-tabs {
        display: flex;
        gap: 4px;
        margin-bottom: 16px;
        flex-wrap: wrap;
    }
    .filter-tab {
        padding: 6px 14px;
        border: 1px solid var(--border, #444);
        border-radius: 6px;
        background: var(--bg-card, #1e1e2e);
        color: var(--text, #eee);
        cursor: pointer;
        font-size: 13px;
    }
    .filter-tab:hover { background: var(--bg-accent, #2a2a3e); }
    .filter-tab.active {
        background: var(--accent, #5a7aff);
        border-color: var(--accent, #5a7aff);
        color: white;
    }
    .search-bar input {
        width: 100%;
        padding: 8px 14px;
        border: 1px solid var(--border, #444);
        border-radius: 6px;
        background: var(--bg-card, #1e1e2e);
        color: var(--text, #eee);
        font-size: 14px;
        margin-bottom: 16px;
        box-sizing: border-box;
    }
    .word-list {
        margin-bottom: 16px;
    }
    .list-header {
        display: flex;
        padding: 8px 0;
        border-bottom: 2px solid var(--border, #444);
        font-size: 12px;
        font-weight: 600;
        color: var(--text-muted, #888);
        text-transform: uppercase;
    }
    .word-row {
        display: flex;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid var(--border-faint, #2a2a3e);
        cursor: pointer;
        background: none;
        border-left: none;
        border-right: none;
        width: 100%;
        text-align: left;
        color: var(--text, #eee);
        font-size: 14px;
    }
    .word-row:hover { background: var(--bg-accent, #252535); }
    .col-rank { width: 60px; font-size: 12px; color: var(--text-muted, #888); }
    .col-word { width: 120px; font-weight: 600; font-size: 16px; }
    .col-reading { flex: 1; color: var(--text-muted, #aaa); }
    .col-freq { width: 100px; font-size: 12px; }
    .col-status { width: 100px; font-size: 12px; }
    .s-known { color: var(--green, #2ecc71); }
    .s-learning { color: var(--orange, #e67e22); }
    .s-ignored { color: var(--gray, #95a5a6); }
    .s-unknown { color: var(--red, #e74c3c); }
    .pagination {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }
    .pagination button {
        padding: 6px 12px;
        border: 1px solid var(--border, #444);
        border-radius: 6px;
        background: var(--bg-card, #1e1e2e);
        color: var(--text, #eee);
        cursor: pointer;
        font-size: 13px;
    }
    .pagination button:hover:not(:disabled) { background: var(--bg-accent, #2a2a3e); }
    .pagination button:disabled { opacity: 0.4; cursor: default; }
    .page-info { font-size: 13px; color: var(--text-muted, #aaa); }
    .page-input {
        width: 50px;
        padding: 4px 8px;
        border: 1px solid var(--border, #444);
        border-radius: 4px;
        background: var(--bg-card, #1e1e2e);
        color: var(--text, #eee);
        text-align: center;
        font-size: 13px;
    }
    .loading, .error, .empty {
        text-align: center;
        padding: 60px 20px;
        color: var(--text-muted, #888);
    }
    .error button {
        margin-left: 10px;
        padding: 4px 12px;
        cursor: pointer;
    }
</style>
```

- [ ] **Step 2: Handle the vocabSearchQuery from other views**

In the script section, add at the top (after imports, before state):

```js
import { app } from './stores.svelte.js';

// If navigated here from "Show in dictionary", pre-fill search
let initialSearch = $state('');
$effect(() => {
    if (app.vocabSearchQuery) {
        initialSearch = app.vocabSearchQuery;
        searchQuery = app.vocabSearchQuery;
        app.vocabSearchQuery = '';
    }
});
```

Change the `$effect` that calls `loadWords()` to use `initialSearch` as a dependency instead of auto-running. Actually, keep it simple — just set `searchQuery` from `app.vocabSearchQuery` on mount:

```js
// Read cross-view search query on mount
if (app.vocabSearchQuery) {
    searchQuery = app.vocabSearchQuery;
    app.vocabSearchQuery = '';
}
```

Add this before `$effect(() => { loadWords(); });`.

- [ ] **Step 3: Build frontend**

```bash
cd src/langmine/web/frontend && npm run build && cd -
```

Expected: No build errors.

- [ ] **Step 4: Commit**

```bash
git add src/langmine/web/frontend/src/lib/VocabPage.svelte
git commit -m "feat: rewrite VocabPage with SUBTLEX data, pagination, popover integration"
```

---

### Task 10: Integration tests and final verification

**Files:**
- Create/Modify: Playwright E2E tests in `src/langmine/web/frontend/tests/`
- Verify: Architecture checks

- [ ] **Step 1: Run full backend test suite**

```bash
source .venv/bin/activate && python -m pytest tests/ -v --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py
```

Expected: All tests PASS.

- [ ] **Step 2: Run architecture checks**

```bash
source .venv/bin/activate && python -m pytest tests/test_architecture.py -v
```

Expected: All architecture rules PASS (domain/ doesn't import adapters, etc.).

- [ ] **Step 3: Verify app starts**

```bash
source .venv/bin/activate && timeout 5 langmine --port 8099 2>&1 || true
```

Expected: Server starts without errors.

- [ ] **Step 4: Manual curl test of the new endpoint**

```bash
# Start the app in background, then:
curl -s http://127.0.0.1:8099/api/vocab/subtlex?per_page=3 | python -m json.tool | head -40
```

Expected: Returns 3 words with all fields populated.

- [ ] **Step 5: Write Playwright E2E test**

In `src/langmine/web/frontend/tests/vocab.spec.js`:

```js
import { test, expect } from '@playwright/test';

test('vocab page loads SUBTLEX words', async ({ page }) => {
    await page.goto('/');
    // Navigate to vocab page
    await page.click('button:has-text("Vocabulary")');
    // Wait for words to load
    await page.waitForSelector('.word-row');
    // First word should be 的
    const firstWord = await page.textContent('.word-row:first-child .col-word');
    expect(firstWord.trim()).toBe('的');
    // Should have pagination
    await expect(page.locator('.pagination')).toBeVisible();
    // Should have filter tabs
    await expect(page.locator('.filter-tab').first()).toBeVisible();
});

test('vocab page popover opens on click', async ({ page }) => {
    await page.goto('/');
    await page.click('button:has-text("Vocabulary")');
    await page.waitForSelector('.word-row');
    await page.click('.word-row:first-child');
    // Popover should appear
    await expect(page.locator('.word-popover')).toBeVisible();
    // Should show definitions
    await expect(page.locator('.word-definitions')).toBeVisible();
    // Close with Escape
    await page.keyboard.press('Escape');
    await expect(page.locator('.word-popover')).not.toBeVisible();
});

test('vocab page pagination works', async ({ page }) => {
    await page.goto('/');
    await page.click('button:has-text("Vocabulary")');
    await page.waitForSelector('.word-row');
    // Navigate to page 2
    await page.click('button:has-text("Next")');
    // First word on page 2 should have rank 101
    const rank = await page.textContent('.word-row:first-child .col-rank');
    expect(rank.trim()).toBe('101');
});

test('vocab page filter tabs work', async ({ page }) => {
    await page.goto('/');
    await page.click('button:has-text("Vocabulary")');
    await page.waitForSelector('.word-row');
    // Click "Known" filter
    await page.click('.filter-tab:has-text("Known")');
    // Should still have a word list (even if empty)
    await expect(page.locator('.word-list, .empty')).toBeVisible();
});
```

- [ ] **Step 6: Run E2E tests**

```bash
cd src/langmine/web/frontend && npx playwright test tests/vocab.spec.js && cd -
```

Expected: Tests PASS (or note any that need the Playwright fake server to be updated with the new endpoint).

- [ ] **Step 7: Commit**

```bash
git add tests/ src/langmine/web/frontend/tests/
git commit -m "test: add integration and E2E tests for SUBTLEX vocab page"
```

