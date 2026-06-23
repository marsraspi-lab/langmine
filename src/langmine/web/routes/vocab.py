"""Vocabulary management API routes."""

from flask import Blueprint, jsonify, request

from ._helpers import (
    _get_dictionary,
    _get_frequency_source,
    _get_language_code,
    _get_persistence,
    _get_processor,
    _sentence_to_dict,
    _unknown_word_dict,
    _vocab_to_dict,
)

vocab_bp = Blueprint("vocab", __name__)


@vocab_bp.route("/api/vocab")
def list_vocab():
    """Paginated vocabulary list with filtering and sorting."""
    persistence = _get_persistence()
    lang = _get_language_code()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 200, type=int)
    status = request.args.get("status")
    search = request.args.get("search")
    sort = request.args.get("sort", "frequency")

    words, total = persistence.list_vocab(
        page=page,
        per_page=per_page,
        status=status,
        search=search,
        sort=sort,
        language_code=lang,
    )

    return jsonify(
        {
            "words": [_vocab_to_dict(w, persistence) for w in words],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    )


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
        enriched.append(
            {
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
            }
        )

    stats = persistence.get_vocab_stats(lang)
    known_count = stats.get("known", 0)
    learning_count = stats.get("learning", 0)
    ignored_count = stats.get("ignored", 0)
    proper_name_count = stats.get("proper_name", 0)
    unknown_count = (
        total_subtlex - known_count - learning_count - ignored_count - proper_name_count
    )

    return jsonify(
        {
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
        }
    )


@vocab_bp.route("/api/vocab/statuses")
def vocab_statuses():
    """Return all vocab words grouped by status for client hashmap init."""
    persistence = _get_persistence()
    lang = _get_language_code()
    all_words, _ = persistence.list_vocab(page=1, per_page=99999, language_code=lang)
    result: dict[str, list[str]] = {"known": [], "learning": [], "ignored": []}
    for word in all_words:
        if word.status in result:
            result[word.status].append(word.word_simplified)
    return jsonify(result)


@vocab_bp.route("/api/vocab/<word>")
def get_vocab_word(word: str):
    """Full detail for a single word: definitions, sentences, stats."""
    persistence = _get_persistence()

    vocab = persistence.get_vocab_word(word)
    sentences = persistence.get_sentences_by_word(word)

    return jsonify(
        {
            "word": _vocab_to_dict(vocab, persistence)
            if vocab
            else _unknown_word_dict(word, persistence),
            "sentences": [
                _sentence_to_dict(s, persistence, processor=_get_processor())
                for s in sentences
            ],
        }
    )


@vocab_bp.route("/api/vocab/<word>", methods=["PATCH"])
def update_vocab_word(word: str):
    """Update a word's status and cascade reclassification."""
    persistence = _get_persistence()
    _get_processor()
    lang = _get_language_code()

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    # Handle "dismiss proper name" action
    if data.get("proper_name") is False:
        _dismiss_proper_name(persistence, word, lang)
        word_obj = persistence.get_vocab_word(word)
        return jsonify({"word": _vocab_to_dict(word_obj, persistence), "ok": True})

    # Handle "mark as proper name" action
    if data.get("proper_name") is True:
        _mark_proper_name(persistence, word, lang)
        word_obj = persistence.get_vocab_word(word)
        return jsonify({"word": _vocab_to_dict(word_obj, persistence), "ok": True})

    if "status" not in data:
        return jsonify({"error": "Missing 'status' field"}), 400

    new_status = data["status"]
    if new_status not in ("known", "learning", "ignored", "proper-name"):
        return jsonify(
            {"error": "Status must be 'known', 'learning', 'ignored', or 'proper-name'"}
        ), 400

    _apply_word_status(persistence, word, lang, new_status)
    word_obj = persistence.get_vocab_word(word)
    return jsonify({"word": _vocab_to_dict(word_obj, persistence), "ok": True})


def _dismiss_proper_name(persistence, word, lang):
    """Dismiss a proper-name classification."""
    persistence.update_vocab_status(word, "learning", lang)
    persistence.log_event(
        entity_type="word",
        entity_id=0,
        action="dismissed_proper_name",
        old_value="proper-name",
        new_value="learning",
        language_code=lang,
    )


def _mark_proper_name(persistence, word, lang):
    """Mark a word as a proper name."""
    existing = persistence.get_vocab_word(word)
    persistence.update_vocab_status(word, "proper-name", lang)
    persistence.log_event(
        entity_type="word",
        entity_id=0,
        action="marked_proper_name",
        old_value=existing.status if existing else "unknown",
        new_value="proper-name",
        language_code=lang,
    )


def _apply_word_status(persistence, word, lang, new_status):
    """Apply a word status change, upserting the word if needed."""
    persistence.update_vocab_status(word, new_status, lang)
    persistence.log_event(
        entity_type="word",
        entity_id=0,
        action=f"marked_{new_status}",
        new_value=word,
        language_code=lang,
    )
