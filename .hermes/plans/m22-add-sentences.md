# M22: Add Sentences + Reclassification

**Goal:** Replace the old `max_cards` mining cap with a paginated "Add Sentences"
model. A reclassification endpoint re-runs sentence classification with current
`known_words`, returning sentences sorted by best-candidate-first. The frontend
loads 50 at a time via an "Add Sentences" button.

**Design:**
- `GET /api/videos/<id>/sentences` already returns all sentences (no change)
- `POST /api/videos/<id>/reclassify` — new endpoint that re-runs classification
  on ALL sentences, saves updated statuses, returns paginated (50 per page)
  sorted by `(unknown_count ASC, frequency_rank ASC)`
- Frontend: "Add Sentences" button replaces the sentence list with
  reclassified results, paginated

---

## Task 1: `POST /api/videos/<id>/reclassify` endpoint

**File:** `src/langmine/web/routes.py`

```python
@app.route("/api/videos/<int:video_id>/reclassify", methods=["POST"])
def reclassify_sentences(video_id: int):
    """Re-run classification on all sentences for a video.

    Uses the current known_words set (which may have changed
    since the initial mine via HSK bootstrap or user marking).
    Returns sentences sorted by (unknown_count ASC, frequency_rank ASC),
    paginated via offset/limit query params.
    """
    persistence = _get_persistence()
    lang = _get_language_code()
    processor = _get_processor()

    # Get all sentences
    sentences = persistence.get_sentences_by_video(video_id, language_code=lang)

    # Re-classify
    classifier = SentenceClassifier(processor, persistence)
    classifier.classify_sentences(sentences)  # updates .status in-place

    # Save updated statuses
    for s in sentences:
        persistence.update_sentence_status(s.id, s.status)

    # Sort: unknown_count ASC, frequency_rank ASC
    sorted_sentences = sorted(sentences, key=_sort_key)

    # Paginate
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 50, type=int)
    page = sorted_sentences[offset:offset + limit]

    return jsonify({
        "video_id": video_id,
        "total": len(sorted_sentences),
        "offset": offset,
        "limit": limit,
        "sentences": [_sentence_to_dict(s, persistence, processor=processor)
                      for s in page],
    })
```

Need helper:

```python
def _sort_key(sentence):
    """Sort by unknown_count ASC, then frequency_rank ASC."""
    unknown_count = ...  # count tokens not in known_words
    rank = sentence.unknown_word_rank or 999999
    return (unknown_count, rank)
```

Actually, looking at the SentenceClassifier, let me check what methods are available...

Let me use `classifier.classify()` but it expects `Sentences` not `Sentence` objects.
Need to check the actual classifier API.

## Task 2: Frontend "Add Sentences" button

**Files:**
- `src/langmine/web/frontend/src/lib/api.js` — add `reclassifySentences()`
- `src/langmine/web/frontend/src/lib/stores.js` — add `reclassifyAndLoad()`
- `src/langmine/web/frontend/src/lib/CardList.svelte` — add button

## Task 3: Tests + E2E

- Backend: test reclassify endpoint in `tests/test_routes.py`
- E2E: test "Add Sentences" button in `e2e/app.spec.js`

## Task 4: Commit M22
