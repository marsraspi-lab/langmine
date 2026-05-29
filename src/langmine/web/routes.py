"""Flask routes for the LangMine curation API."""

import os
from flask import (
    Flask, jsonify, request, send_file, send_from_directory, current_app,
)

from langmine.domain.models import Video, Sentence
from langmine.domain.ports import (
    Persistence, LanguageProcessor, TranscriptSource, AudioProcessor,
)


VALID_SENTENCE_STATUSES = {"kept", "deleted"}
EDITABLE_FIELDS = {"pinyin", "translation_de", "text_segmented"}


def register_routes(app: Flask):
    """Register all API and page routes on the Flask app."""

    # === Page Routes ===

    @app.route("/")
    def index():
        """Serve the Svelte SPA."""
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        return send_from_directory(static_dir, "index.html")

    # === API Routes ===

    @app.route("/api/videos")
    def list_videos():
        """List all videos with sentence counts by status."""
        persistence = _get_persistence()
        videos = persistence.list_videos()

        return jsonify({
            "videos": [
                _video_with_counts(persistence, v)
                for v in videos
            ]
        })

    @app.route("/api/videos/mine", methods=["POST"])
    def mine_video():
        """Mine a YouTube video: transcript → merge → classify → persist.

        Accepts JSON with 'url' or multipart/form-data with 'url' + optional
        transcript file (.srt/.vtt). When a transcript file is provided, it
        is used directly instead of calling youtube-transcript-api.
        """
        persistence = _get_persistence()
        processor = _get_processor()
        audio = _get_audio_processor()

        # Determine which transcript source to use
        transcript = _get_transcript_source()

        # Handle multipart form data (with optional file upload)
        if request.content_type and "multipart" in request.content_type:
            url = request.form.get("url", "").strip()
            if not url:
                return jsonify({"error": "Missing 'url' field"}), 400

            file = request.files.get("file")
            if file and file.filename:
                InlineTranscriptSource = current_app.config.get(
                    "LANGMINE_INLINE_TRANSCRIPT_CLASS"
                )
                parse_subtitle_file = current_app.config.get(
                    "LANGMINE_PARSE_SUBTITLE_FILE"
                )
                if InlineTranscriptSource and parse_subtitle_file:
                    content = file.read().decode("utf-8")
                    chunks = parse_subtitle_file(content, filename=file.filename)
                    if not chunks:
                        return jsonify({"error": "No subtitle entries found in uploaded file"}), 400
                    transcript = InlineTranscriptSource(chunks)
        else:
            # JSON body (backward compatible)
            data = request.get_json(silent=True)
            if not data or "url" not in data:
                return jsonify({"error": "Missing 'url' field"}), 400
            url = data["url"]

        # Extract video ID (simple extraction, same as transcript module)
        from langmine.transcript import _extract_video_id
        video_id = _extract_video_id(url)

        try:
            from langmine.pipeline import process_video
            from langmine.config import load_config

            config = load_config()
            output_dir = config.data_dir
            os.makedirs(output_dir, exist_ok=True)

            result = process_video(
                transcript_source=transcript,
                audio_processor=audio,
                persistence=persistence,
                language_processor=processor,
                video_id=video_id,
                output_dir=output_dir,
            )

            # Find the video we just created
            video = persistence.get_video(video_id)

            return jsonify({
                "video_id": video.id if video else None,
                "youtube_id": video_id,
                "i1_candidates": len(result["i1_candidates"]),
                "i0_count": result["i0_count"],
                "stash_count": result["stash_count"],
                "total_sentences": result["total_sentences"],
                "i1_count": len(result["i1_candidates"]),
            })

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Mining failed: {e}"}), 500

    @app.route("/api/videos/<int:video_id>/sentences")
    def get_sentences(video_id: int):
        """Get sentences for a video, optionally filtered by status."""
        persistence = _get_persistence()
        status = request.args.get("status")

        sentences = persistence.get_sentences_by_video(video_id, status=status)

        return jsonify({
            "video_id": video_id,
            "filter_status": status,
            "sentences": [_sentence_to_dict(s, persistence) for s in sentences],
        })

    @app.route("/api/videos/<int:video_id>/transcript")
    def get_transcript(video_id: int):
        """Return all sentences in time-order for the reading view."""
        persistence = _get_persistence()
        sentences = persistence.get_sentences_by_video(video_id)
        # Sort chronologically for reading order
        sentences.sort(key=lambda s: s.start_ms)
        return jsonify({
            "video_id": video_id,
            "sentences": [_sentence_to_dict(s, persistence) for s in sentences],
        })

    @app.route("/api/sentences/<int:sentence_id>", methods=["PATCH"])
    def update_sentence(sentence_id: int):
        """Update sentence fields: status, pinyin, translation_de, text_segmented.

        text_segmented changes trigger re-classification of unknown words.
        """
        persistence = _get_persistence()

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Missing request body"}), 400

        sentence = _find_sentence(persistence, sentence_id)
        if sentence is None:
            return jsonify({"error": "Sentence not found"}), 404

        # --- Status update (existing behavior) ---
        if "status" in data:
            status = data["status"]
            if status not in VALID_SENTENCE_STATUSES:
                return jsonify({
                    "error": f"Invalid status '{status}'. Must be one of: {sorted(VALID_SENTENCE_STATUSES)}"
                }), 400
            sentence.status = status
            # If keeping, mark unknown word as "learning"
            if status == "kept" and sentence.unknown_word:
                persistence.mark_word_learning(sentence.unknown_word)

        # --- Field edits ---
        edited = False
        for field in EDITABLE_FIELDS:
            if field in data:
                setattr(sentence, field, data[field])
                edited = True

        # Re-classify if segmentation changed
        if "text_segmented" in data and sentence.status not in ("exported", "deleted"):
            _reclassify_from_segmented(persistence, sentence)

        if edited or "status" in data:
            persistence.update_sentence(sentence)

        return jsonify({
            "sentence": _sentence_to_dict(sentence, persistence),
        })

    @app.route("/api/sentences/<int:sentence_id>/iknowthis", methods=["PATCH"])
    def mark_word_known(sentence_id: int):
        """Mark the unknown word in this sentence as known.

        Also reclassifies the sentence to i0 if it was i1.
        """
        persistence = _get_persistence()
        processor = _get_processor()

        sentence = _find_sentence(persistence, sentence_id)
        if sentence is None:
            return jsonify({"error": "Sentence not found"}), 404

        if sentence.unknown_word is None:
            return jsonify({"error": "Sentence has no unknown word to mark as known"}), 400

        word = sentence.unknown_word
        persistence.mark_word_known(word)

        # Re-classify: with the word now known, this sentence should be i0
        sentence.status = "i0"
        persistence.update_sentence(sentence)

        return jsonify({
            "word_marked": word,
            "sentence": _sentence_to_dict(sentence, persistence),
        })

    @app.route("/api/sentences/<int:sentence_id>/audio")
    def serve_audio(sentence_id: int):
        """Serve the audio clip for a sentence."""
        persistence = _get_persistence()
        sentence = _find_sentence(persistence, sentence_id)
        if sentence is None:
            return jsonify({"error": "Sentence not found"}), 404

        if not sentence.audio_clip_path or not os.path.exists(sentence.audio_clip_path):
            return jsonify({"error": "Audio file not found"}), 404

        return send_file(
            sentence.audio_clip_path,
            mimetype="audio/mpeg",
            as_attachment=False,
        )

    @app.route("/api/sentences/<int:sentence_id>/screenshot")
    def serve_screenshot(sentence_id: int):
        """Serve the screenshot for a sentence."""
        persistence = _get_persistence()
        sentence = _find_sentence(persistence, sentence_id)
        if sentence is None:
            return jsonify({"error": "Sentence not found"}), 404

        if not sentence.screenshot_path or not os.path.exists(sentence.screenshot_path):
            return jsonify({"error": "Screenshot not found"}), 404

        return send_file(
            sentence.screenshot_path,
            mimetype="image/jpeg",
            as_attachment=False,
        )

    # === Vocab API ===

    @app.route("/api/vocab")
    def list_vocab():
        """Paginated vocabulary list with filtering and sorting."""
        persistence = _get_persistence()

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 200, type=int)
        status = request.args.get("status")
        search = request.args.get("search")
        sort = request.args.get("sort", "frequency")

        words, total = persistence.list_vocab(
            page=page, per_page=per_page, status=status,
            search=search, sort=sort,
        )

        return jsonify({
            "words": [_vocab_to_dict(w, persistence) for w in words],
            "total": total,
            "page": page,
            "per_page": per_page,
        })

    @app.route("/api/vocab/<word>")
    def get_vocab_word(word: str):
        """Full detail for a single word: definitions, sentences, stats."""
        persistence = _get_persistence()

        vocab = persistence.get_vocab_word(word)
        sentences = persistence.get_sentences_by_word(word)

        return jsonify({
            "word": _vocab_to_dict(vocab, persistence) if vocab else _unknown_word_dict(word, persistence),
            "sentences": [_sentence_to_dict(s, persistence) for s in sentences],
        })

    @app.route("/api/vocab/<word>", methods=["PATCH"])
    def update_vocab_word(word: str):
        """Update a word's status and cascade reclassification."""
        persistence = _get_persistence()
        processor = _get_processor()

        data = request.get_json(silent=True)
        if not data or "status" not in data:
            return jsonify({"error": "Missing 'status' field"}), 400

        new_status = data["status"]
        if new_status not in ("known", "learning"):
            return jsonify({"error": "Status must be 'known' or 'learning'"}), 400

        if new_status == "known":
            persistence.mark_word_known(word)
            # Cascade: reclassify sentences where this word was the i+1 target
            _cascade_word_known(persistence, word)
        else:
            persistence.mark_word_learning(word)

        return jsonify({
            "word": word,
            "status": new_status,
            "ok": True,
        })

    @app.route("/api/stats")
    def stats():
        """Return vocabulary stats."""
        persistence = _get_persistence()
        return jsonify(persistence.get_vocab_stats())

    @app.route("/api/config")
    def get_config():
        """Return current configuration (sanitized — no API keys)."""
        from langmine.config import load_config
        config = load_config()
        return jsonify({
            "anki_connect_url": config.anki_connect_url,
            "deck_name": config.deck_name,
            "note_type": config.note_type,
            "source_language": config.source_language,
            "target_language": config.target_language,
            "translation_api": config.translation_api,
            "sentence_gap_ms": config.sentence_gap_ms,
            "audio_pad_before_ms": config.audio_pad_before_ms,
            "audio_pad_after_ms": config.audio_pad_after_ms,
            "max_cards_per_video": config.max_cards_per_video,
            "max_stash_cards": config.max_stash_cards,
            "hsk_bootstrap": config.hsk_bootstrap,
        })

    @app.route("/api/config", methods=["PUT"])
    def update_config():
        """Update configuration and save to config.yaml."""
        from langmine.config import load_config, save_config

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Missing request body"}), 400

        # Allowed config keys
        ALLOWED = {
            "anki_connect_url", "deck_name", "note_type",
            "source_language", "target_language", "translation_api",
            "sentence_gap_ms", "audio_pad_before_ms", "audio_pad_after_ms",
            "max_cards_per_video", "max_stash_cards", "hsk_bootstrap",
            "deepl_api_key",
        }

        config = load_config()
        for key, value in data.items():
            if key in ALLOWED:
                setattr(config, key, value)

        save_config(config)
        return jsonify({"ok": True})

    @app.route("/api/export/anki", methods=["POST"])
    def export_anki():
        """Export kept sentences directly to Anki via AnkiConnect."""
        persistence = _get_persistence()
        exporter = current_app.config.get("LANGMINE_ANKI_EXPORTER")

        if exporter is None:
            return jsonify({
                "error": "Anki exporter not configured."
            }), 503

        data = request.get_json(silent=True) or {}
        video_id = data.get("video_id")
        all_kept = data.get("all_kept", False)
        force_update = data.get("force_update_model", False)

        if video_id is not None:
            sentences = persistence.get_sentences_by_video(
                video_id, status="kept"
            )
        elif all_kept:
            sentences = persistence.get_sentences_by_status("kept")
        else:
            return jsonify({
                "error": "Specify video_id or all_kept=true"
            }), 400

        if not sentences:
            return jsonify({
                "error": "No kept sentences to export"
            }), 400

        try:
            from langmine.config import load_config
            config = load_config()
            result = exporter.export(
                sentences=sentences,
                deck_name=config.deck_name,
                note_type_name=config.note_type,
                card_css=config.card_css,
                card_front=config.card_front_template,
                card_back=config.card_back_template,
                force_update_model=force_update,
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


# === Helpers ===


def _get_persistence() -> Persistence:
    """Get the persistence port from app config."""
    return current_app.config["LANGMINE_PERSISTENCE"]


def _get_processor() -> LanguageProcessor | None:
    """Get the language processor port from app config."""
    return current_app.config.get("LANGMINE_LANGUAGE_PROCESSOR")


def _get_transcript_source() -> TranscriptSource | None:
    """Get the transcript source port from app config."""
    return current_app.config.get("LANGMINE_TRANSCRIPT_SOURCE")


def _get_audio_processor() -> AudioProcessor | None:
    """Get the audio processor port from app config."""
    return current_app.config.get("LANGMINE_AUDIO_PROCESSOR")


def _reclassify_from_segmented(
    persistence: Persistence,
    sentence: Sentence,
) -> None:
    """Re-classify a sentence based on its manually-edited text_segmented.

    Parses the "word / word / word" format, filters non-words, and
    counts unknown words against the known vocabulary. Updates
    sentence.status, sentence.unknown_word, and sentence.unknown_word_rank.
    """
    processor = _get_processor()
    if processor is None:
        return

    known_words = persistence.get_known_words()

    # Parse tokens from "word1 / word2 / word3"
    tokens = [t.strip() for t in sentence.text_segmented.split(" / ") if t.strip()]

    # Filter non-words
    content_words = [t for t in tokens if not processor.is_non_word(t)]

    # Count unknowns
    unknown_words = [w for w in content_words if w not in known_words]
    unknown_count = len(unknown_words)

    if unknown_count == 0:
        sentence.status = "i0"
        sentence.unknown_word = None
        sentence.unknown_word_rank = None
    elif unknown_count == 1:
        word = unknown_words[0]
        sentence.status = "i1"
        sentence.unknown_word = word
        sentence.unknown_word_rank = processor.get_frequency(word)
    else:
        sentence.status = "stashed"
        sentence.unknown_word = None
        sentence.unknown_word_rank = None


def _find_sentence(persistence: Persistence, sentence_id: int) -> Sentence | None:
    """Find a sentence by id across all videos. Brute-force for simplicity."""
    for video in persistence.list_videos():
        sentences = persistence.get_sentences_by_video(video.id)
        for s in sentences:
            if s.id == sentence_id:
                return s
    return None


def _video_with_counts(persistence: Persistence, video) -> dict:
    """Build a video dict with sentence counts by status."""
    sentences = persistence.get_sentences_by_video(video.id)
    counts = {
        "total": 0, "i1": 0, "i0": 0, "stashed": 0, "kept": 0, "deleted": 0,
    }
    for s in sentences:
        counts["total"] += 1
        if s.status in counts:
            counts[s.status] += 1

    return {
        "id": video.id,
        "youtube_id": video.youtube_id,
        "title": video.title,
        "channel": video.channel,
        "duration_sec": video.duration_sec,
        "total_sentences": counts["total"],
        "i1_count": counts["i1"],
        "i0_count": counts["i0"],
        "stashed_count": counts["stashed"],
        "kept_count": counts["kept"],
        "deleted_count": counts["deleted"],
    }


def _sentence_to_dict(sentence: Sentence, persistence: Persistence | None = None) -> dict:
    """Convert a Sentence domain model to a JSON-safe dict.

    When persistence is provided, enriches with per-word status metadata
    (known/learning/unknown, frequency_rank, hsk_level).
    """
    from langmine.domain.models import frequency_badge

    result = {
        "id": sentence.id,
        "video_id": sentence.video_id,
        "text": sentence.text,
        "text_segmented": sentence.text_segmented,
        "pinyin": sentence.pinyin,
        "translation_de": sentence.translation_de,
        "unknown_word": sentence.unknown_word,
        "unknown_word_rank": sentence.unknown_word_rank,
        "start_ms": sentence.start_ms,
        "end_ms": sentence.end_ms,
        "status": sentence.status,
        "has_audio": bool(sentence.audio_clip_path),
        "has_screenshot": bool(sentence.screenshot_path),
    }

    # Compute frequency badge from rank
    result["frequency_badge"] = frequency_badge(sentence.unknown_word_rank)

    # Enrich with per-word metadata for highlighting
    if persistence is not None:
        result["words"] = _words_array(sentence, persistence)

    return result


def _words_array(sentence: Sentence, persistence: Persistence) -> list[dict]:
    """Build the words[] array for a sentence with status/metadata per token."""
    from langmine.hsk_data import get_hsk_level

    tokens = [t.strip() for t in sentence.text_segmented.split(" / ") if t.strip()]
    if not tokens:
        return []

    known_words = persistence.get_known_words()
    result = []
    for token in tokens:
        vocab = persistence.get_vocab_word(token)
        status = "unknown"
        frequency_rank = None
        hsk_level = get_hsk_level(token)

        if vocab:
            status = vocab.status
            frequency_rank = vocab.frequency_rank
        elif token in known_words:
            status = "known"

        result.append({
            "token": token,
            "status": status,
            "frequency_rank": frequency_rank,
            "hsk_level": hsk_level,
        })
    return result


def _vocab_to_dict(word, persistence: Persistence | None = None) -> dict:
    """Convert a VocabWord to a JSON-safe dict with sentence count."""
    from langmine.hsk_data import get_hsk_level
    from langmine.domain.models import frequency_badge

    sentence_count = 0
    if persistence and word.word_simplified:
        sentences = persistence.get_sentences_by_word(word.word_simplified)
        sentence_count = len(sentences)

    hsk = word.hsk_level or get_hsk_level(word.word_simplified)
    rank = word.frequency_rank

    return {
        "word": word.word_simplified,
        "pinyin": word.pinyin,
        "definition_de": word.definition_de,
        "definition_en": "",  # VocabWord doesn't store EN; filled if needed
        "hsk_level": hsk,
        "frequency_rank": rank,
        "frequency_badge": frequency_badge(rank),
        "status": word.status,
        "sentence_count": sentence_count,
    }


def _unknown_word_dict(word: str, persistence: Persistence) -> dict:
    """Build a vocab dict for a word not yet in the vocab table."""
    from langmine.hsk_data import get_hsk_level
    from langmine.domain.models import frequency_badge

    sentences = persistence.get_sentences_by_word(word)
    hsk = get_hsk_level(word)

    return {
        "word": word,
        "pinyin": "",
        "definition_de": "",
        "definition_en": "",
        "hsk_level": hsk,
        "frequency_rank": None,
        "frequency_badge": "",
        "status": "unknown",
        "sentence_count": len(sentences),
    }


def _cascade_word_known(persistence: Persistence, word: str) -> None:
    """Reclassify all sentences where `word` is the unknown_word.

    - i+1 sentences → i0 (word is now known)
    - Stashed sentences get rechecked via reclassify_stashed per affected video
    """
    sentences = persistence.get_sentences_by_word(word)
    affected_videos: set[int] = set()

    for s in sentences:
        if s.unknown_word == word and s.status == "i1":
            s.status = "i0"
            persistence.update_sentence(s)
            affected_videos.add(s.video_id)

    # Re-run classifier on stashed sentences for affected videos
    for vid in affected_videos:
        persistence.reclassify_stashed(vid)
