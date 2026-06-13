"""Vocabulary management API routes."""

from flask import Blueprint, jsonify, request

from ._helpers import (
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
        return jsonify({"word": word, "status": "learning", "ok": True})

    # Handle "mark as proper name" action
    if data.get("proper_name") is True:
        _mark_proper_name(persistence, word, lang)
        return jsonify({"word": word, "status": "proper-name", "ok": True})

    if "status" not in data:
        return jsonify({"error": "Missing 'status' field"}), 400

    new_status = data["status"]
    if new_status not in ("known", "learning", "ignored", "proper-name"):
        return jsonify(
            {"error": "Status must be 'known', 'learning', 'ignored', or 'proper-name'"}
        ), 400

    _apply_word_status(persistence, word, lang, new_status)
    return jsonify({"word": word, "status": new_status, "ok": True})


def _dismiss_proper_name(persistence, word, lang):
    """Dismiss a proper-name classification, reverting to 'learning'."""
    persistence.mark_word_learning(word)
    persistence.log_event(
        entity_type="word", entity_id=0,
        action="dismissed_proper_name",
        old_value="proper-name", new_value="learning",
        language_code=lang,
    )


def _mark_proper_name(persistence, word, lang):
    """Mark a word as a proper name."""
    existing = persistence.get_vocab_word(word)
    if existing:
        existing.status = "proper-name"
    else:
        from langmine.domain.models import VocabWord
        persistence.save_vocab_word(
            VocabWord(word_simplified=word, status="proper-name", language_code=lang)
        )
    persistence.log_event(
        entity_type="word", entity_id=0,
        action="marked_proper_name",
        old_value=existing.status if existing else "unknown",
        new_value="proper-name",
        language_code=lang,
    )


def _apply_word_status(persistence, word, lang, new_status):
    """Apply a word status change and log the event."""
    actions = {
        "known": ("marked_known", persistence.mark_word_known),
        "ignored": ("marked_ignored", persistence.mark_word_ignored),
        "proper-name": ("marked_proper_name", persistence.mark_word_ignored),
        "learning": ("marked_learning", persistence.mark_word_learning),
    }
    action, handler = actions.get(new_status, ("marked_learning", persistence.mark_word_learning))
    handler(word)
    persistence.log_event(
        entity_type="word", entity_id=0,
        action=action, new_value=word,
        language_code=lang,
    )
