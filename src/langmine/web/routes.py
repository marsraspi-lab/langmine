"""Flask routes for the LangMine curation API."""

import json
import os
from importlib.metadata import version as _pkg_version
from flask import (
    Flask, jsonify, request, send_file, send_from_directory, current_app,
)

from langmine.domain.models import Video, Sentence
from langmine.domain.ports import (
    Persistence, LanguageProcessor, TranscriptSource, AudioProcessor,
    ImageSearch,
)


VALID_SENTENCE_STATUSES = {"kept", "deleted"}
EDITABLE_FIELDS = {"reading", "translation_de", "text_segmented"}


def register_routes(app: Flask):
    """Register all API and page routes on the Flask app."""

    # === Page Routes ===

    @app.route("/")
    def index():
        """Serve the Svelte SPA."""
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        return send_from_directory(static_dir, "index.html")

    # === API Routes ===

    @app.route("/api/version")
    def app_version():
        """Return the installed LangMine version."""
        try:
            v = _pkg_version("langmine")
        except Exception:
            v = "unknown"
        return jsonify({"version": v, "name": "langmine"})

    @app.route("/api/languages")
    def list_languages():
        """List available source languages with code and display name."""
        from langmine.language_factory import get_available_languages
        return jsonify({"languages": get_available_languages()})

    @app.route("/api/videos")
    def list_videos():
        """List all videos with sentence counts by status."""
        persistence = _get_persistence()
        lang = _get_language_code()
        videos = persistence.list_videos(language_code=lang)

        return jsonify({
            "videos": [
                _video_with_counts(persistence, v, lang)
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

            if video and video.id:
                persistence.log_event(
                    entity_type="video", entity_id=video.id,
                    action="mined", new_value=video_id,
                    language_code=config.source_language,
                )

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

    @app.route("/api/videos/preview", methods=["POST"])
    def preview_video():
        """Estimate difficulty for a YouTube video before mining.

        Fetches transcript, segments into sentences, and classifies each
        word against the user's known vocabulary. Does NOT persist anything.
        Returns stats and annotated sentences with word-level highlighting.
        """
        data = request.get_json(silent=True)
        if not data or "url" not in data:
            return jsonify({"error": "Missing 'url' field"}), 400

        url = data["url"].strip()
        if not url:
            return jsonify({"error": "Missing 'url' field"}), 400

        from langmine.transcript import _extract_video_id, merge_sentences
        from langmine.config import load_config

        config = load_config()
        video_id = _extract_video_id(url)

        transcript_source = _get_transcript_source()
        persistence = _get_persistence()
        processor = _get_processor()

        if transcript_source is None or processor is None:
            return jsonify({
                "error": "Transcript source or language processor not configured."
            }), 503

        try:
            chunks = transcript_source.fetch(video_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        merged = merge_sentences(chunks, gap_ms=config.sentence_gap_ms)
        known_words = persistence.get_known_words()

        preview_sentences = []
        total_content_words = 0
        total_known_words = 0
        unknown_counts = []

        for m in merged:
            tokens = processor.segment(m.text)
            # Classify each token
            words = []
            sentence_unknown = 0
            for token in tokens:
                if processor.is_non_word(token):
                    status = "non-word"
                elif token in known_words:
                    status = "known"
                    total_content_words += 1
                    total_known_words += 1
                else:
                    status = "learning"
                    total_content_words += 1
                    sentence_unknown += 1
                words.append({"token": token, "status": status})

            unknown_counts.append(sentence_unknown)

            entry = {
                "text": m.text,
                "text_segmented": " / ".join(tokens),
                "reading": processor.get_reading(m.text),
                "translation_de": processor.translate_sentence(m.text),
                "words": words,
                "start_ms": m.start_ms,
                "end_ms": m.end_ms,
                "unknown_count": sentence_unknown,
            }
            preview_sentences.append(entry)

        total_sentences = len(merged)
        i1_count = sum(1 for u in unknown_counts if u == 1)
        i0_count = sum(1 for u in unknown_counts if u == 0)
        stash_count = sum(1 for u in unknown_counts if u >= 2)
        known_word_pct = round(
            total_known_words / total_content_words * 100, 1
        ) if total_content_words > 0 else 0.0
        avg_unknown = round(
            sum(unknown_counts) / total_sentences, 1
        ) if total_sentences > 0 else 0.0

        return jsonify({
            "total_sentences": total_sentences,
            "i1_estimated": i1_count,
            "i0_count": i0_count,
            "stash_count": stash_count,
            "known_word_pct": known_word_pct,
            "avg_unknown_per_sentence": avg_unknown,
            "sentences": preview_sentences,
        })

    @app.route("/api/videos/<int:video_id>/sentences")
    def get_sentences(video_id: int):
        """Get sentences for a video, optionally filtered by status."""
        persistence = _get_persistence()
        lang = _get_language_code()
        status = request.args.get("status")

        sentences = persistence.get_sentences_by_video(video_id, status=status, language_code=lang)

        return jsonify({
            "video_id": video_id,
            "filter_status": status,
            "sentences": [_sentence_to_dict(s, persistence) for s in sentences],
        })

    @app.route("/api/videos/<int:video_id>/transcript")
    def get_transcript(video_id: int):
        """Return all sentences in time-order for the reading view."""
        persistence = _get_persistence()
        lang = _get_language_code()
        sentences = persistence.get_sentences_by_video(video_id, language_code=lang)
        # Sort chronologically for reading order
        sentences.sort(key=lambda s: s.start_ms)
        return jsonify({
            "video_id": video_id,
            "sentences": [_sentence_to_dict(s, persistence) for s in sentences],
        })

    @app.route("/api/sentences/<int:sentence_id>", methods=["PATCH"])
    def update_sentence(sentence_id: int):
        """Update sentence fields: status, reading, translation_de, text_segmented.

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
            old_status = sentence.status
            status = data["status"]
            if status not in VALID_SENTENCE_STATUSES:
                return jsonify({
                    "error": f"Invalid status '{status}'. Must be one of: {sorted(VALID_SENTENCE_STATUSES)}"
                }), 400
            sentence.status = status
            # If keeping, mark unknown word as "learning"
            if status == "kept" and sentence.unknown_word:
                persistence.mark_word_learning(sentence.unknown_word)

            # Log the status change event
            persistence.log_event(
                entity_type="sentence", entity_id=sentence.id,
                action=status, old_value=old_status, new_value=status,
                language_code=sentence.language_code,
            )

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

        # Log field edits separately (only if edited without status change)
        if edited and "status" not in data:
            persistence.log_event(
                entity_type="sentence", entity_id=sentence.id,
                action="edited", new_value=",".join(
                    f for f in EDITABLE_FIELDS if f in data
                ),
                language_code=sentence.language_code,
            )

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

        persistence.log_event(
            entity_type="word", entity_id=sentence.id,
            action="marked_known", new_value=word,
            language_code=sentence.language_code,
        )

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

    # === Image Search API (M12) ===

    @app.route("/api/images/search")
    def search_images():
        """Search for images of a word. Query params: q, count (default 5)."""
        searcher = _get_image_searcher()
        if searcher is None:
            return jsonify({"error": "Image search not configured."}), 503

        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"error": "Missing 'q' query parameter."}), 400

        count = request.args.get("count", 5, type=int)
        try:
            urls = searcher.search(query, count=count)
            return jsonify({"query": query, "images": urls})
        except Exception as e:
            return jsonify({"error": f"Image search failed: {e}"}), 500

    @app.route("/api/sentences/<int:sentence_id>/cloze-image", methods=["POST"])
    def set_cloze_image(sentence_id: int):
        """Store a user-selected cloze hint image URL for a sentence."""
        persistence = _get_persistence()
        sentence = _find_sentence(persistence, sentence_id)
        if sentence is None:
            return jsonify({"error": "Sentence not found"}), 404

        data = request.get_json(silent=True)
        if not data or "image_url" not in data:
            return jsonify({"error": "Missing 'image_url' field"}), 400

        sentence.cloze_image_url = data["image_url"]
        persistence.update_sentence(sentence)

        return jsonify({
            "ok": True,
            "sentence_id": sentence_id,
            "cloze_image_url": sentence.cloze_image_url,
        })

    @app.route("/api/sentences/<int:sentence_id>/annotation", methods=["PATCH"])
    def update_annotation(sentence_id: int):
        """Update a single annotation entry for a sentence.

        Accepts {index, char?, reading?, tone?, definition?}.
        Updates the annotation_json entry at the given index and persists.
        """
        persistence = _get_persistence()
        sentence = _find_sentence(persistence, sentence_id)
        if sentence is None:
            return jsonify({"error": "Sentence not found"}), 404

        data = request.get_json(silent=True)
        if not data or "index" not in data:
            return jsonify({"error": "Missing 'index' field"}), 400

        index = data["index"]

        # Parse existing annotation data
        try:
            annotation = json.loads(sentence.annotation_json or "[]")
        except (json.JSONDecodeError, TypeError):
            annotation = []

        if not isinstance(annotation, list) or index < 0 or index >= len(annotation):
            return jsonify({
                "error": f"Index {index} out of range (0-{len(annotation) - 1 if annotation else -1})"
            }), 400

        entry = annotation[index]
        for field in ("char", "pinyin", "tone", "definition"):
            if field in data:
                entry[field] = data[field]

        sentence.annotation_json = json.dumps(annotation)
        persistence.update_sentence(sentence)

        persistence.log_event(
            entity_type="sentence", entity_id=sentence.id,
            action="annotation_edited", new_value=str(index),
            language_code=sentence.language_code,
        )

        return jsonify({"ok": True, "annotation": annotation})

    # === Vocab API ===

    @app.route("/api/vocab")
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
            page=page, per_page=per_page, status=status,
            search=search, sort=sort, language_code=lang,
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
        lang = _get_language_code()

        data = request.get_json(silent=True)
        if not data or "status" not in data:
            return jsonify({"error": "Missing 'status' field"}), 400

        new_status = data["status"]
        if new_status not in ("known", "learning", "ignored"):
            return jsonify({"error": "Status must be 'known', 'learning', or 'ignored'"}), 400

        if new_status == "known":
            persistence.mark_word_known(word)
            persistence.log_event(
                entity_type="word", entity_id=0,
                action="marked_known", new_value=word,
                language_code=lang,
            )
            # Cascade: reclassify sentences where this word was the i+1 target
            _cascade_word_known(persistence, word, processor)
        elif new_status == "ignored":
            persistence.mark_word_ignored(word)
            persistence.log_event(
                entity_type="word", entity_id=0,
                action="marked_ignored", new_value=word,
                language_code=lang,
            )
            # Cascade: reclassify sentences where this word was the i+1 target
            _cascade_word_known(persistence, word, processor)
        else:
            persistence.mark_word_learning(word)
            persistence.log_event(
                entity_type="word", entity_id=0,
                action="marked_learning", new_value=word,
                language_code=lang,
            )

        return jsonify({
            "word": word,
            "status": new_status,
            "ok": True,
        })

    @app.route("/api/stats")
    def stats():
        """Return vocabulary stats."""
        persistence = _get_persistence()
        lang = _get_language_code()
        return jsonify(persistence.get_vocab_stats(language_code=lang))

    @app.route("/api/config")
    def get_config():
        """Return current configuration (sanitized — no API keys)."""
        from langmine.config import load_config
        config = load_config()
        return jsonify({
            "anki_connect_url": config.anki_connect_url,
            "source_language": config.source_language,
            "target_language": config.target_language,
            "translation_api": config.translation_api,
            "sentence_gap_ms": config.sentence_gap_ms,
            "audio_pad_before_ms": config.audio_pad_before_ms,
            "audio_pad_after_ms": config.audio_pad_after_ms,
            "max_cards_per_video": config.max_cards_per_video,
            "max_stash_cards": config.max_stash_cards,
            "user_agent": config.user_agent,
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
            "anki_connect_url",
            "source_language", "target_language", "translation_api",
            "sentence_gap_ms", "audio_pad_before_ms", "audio_pad_after_ms",
            "max_cards_per_video", "max_stash_cards",
            "deepl_api_key",
            "user_agent",
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
        card_type = data.get("card_type", "basic")

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
            from langmine.language_factory import get_anki_templates, get_language_manifest

            lang = _get_language_code()
            manifest = get_language_manifest(lang)
            templates = get_anki_templates(lang)

            # Select templates based on card type
            if card_type == "cloze":
                note_type = manifest.get("cloze_note_type", "LangMine Cloze")
                css = templates.get("cloze_css", "")
                front = templates.get("cloze_front", "")
                back = templates.get("cloze_back", "")
            else:
                note_type = manifest.get("note_type", "LangMine Sentence")
                css = templates.get("basic_css", "")
                front = templates.get("basic_front", "")
                back = templates.get("basic_back", "")

            result = exporter.export(
                sentences=sentences,
                deck_name=manifest.get("deck_name", "LangMine"),
                note_type_name=note_type,
                card_css=css,
                card_front=front,
                card_back=back,
                force_update_model=force_update,
                card_type=card_type,
            )

            # Mark exported sentences
            lang = _get_language_code()
            for s in sentences:
                s.status = "exported"
                persistence.update_sentence(s)
                persistence.log_event(
                    entity_type="sentence", entity_id=s.id or 0,
                    action="exported", old_value="kept", new_value="exported",
                    language_code=lang,
                )

            return jsonify(result)
        except ConnectionError as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            return jsonify({"error": f"Export failed: {e}"}), 500


# === Helpers ===


def _get_language_code() -> str:
    """Get the current source language from config."""
    from langmine.config import load_config
    return load_config().source_language


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


def _get_image_searcher() -> ImageSearch | None:
    """Get the image search port from app config."""
    return current_app.config.get("LANGMINE_IMAGE_SEARCHER")


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


def _video_with_counts(persistence: Persistence, video, lang: str = "") -> dict:
    """Build a video dict with sentence counts by status."""
    sentences = persistence.get_sentences_by_video(video.id, language_code=lang)
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
        "reading": sentence.reading,
        "translation_de": sentence.translation_de,
        "unknown_word": sentence.unknown_word,
        "unknown_word_rank": sentence.unknown_word_rank,
        "start_ms": sentence.start_ms,
        "end_ms": sentence.end_ms,
        "status": sentence.status,
        "has_audio": bool(sentence.audio_clip_path),
        "has_screenshot": bool(sentence.screenshot_path),
        "created_at": sentence.created_at,
        "updated_at": sentence.updated_at,
    }

    # Compute frequency badge from rank
    result["frequency_badge"] = frequency_badge(sentence.unknown_word_rank)

    # Annotations — parse JSON, fallback to empty list
    try:
        result["annotation"] = json.loads(sentence.annotation_json) if sentence.annotation_json else []
    except (json.JSONDecodeError, TypeError):
        result["annotation"] = []

    # Enrich with per-word metadata for highlighting
    if persistence is not None:
        result["words"] = _words_array(sentence, persistence)

    return result


def _words_array(sentence: Sentence, persistence: Persistence) -> list[dict]:
    """Build the words[] array for a sentence with status/metadata per token."""
    from langmine.language_factory import get_proficiency_level as get_hsk_level

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
    from langmine.language_factory import get_proficiency_level as get_hsk_level
    from langmine.domain.models import frequency_badge

    sentence_count = 0
    if persistence and word.word_simplified:
        sentences = persistence.get_sentences_by_word(word.word_simplified)
        sentence_count = len(sentences)

    hsk = word.hsk_level or get_hsk_level(word.word_simplified)
    rank = word.frequency_rank

    return {
        "word": word.word_simplified,
        "reading": word.reading,
        "definition_de": word.definition_de,
        "definition_en": "",  # VocabWord doesn't store EN; filled if needed
        "hsk_level": hsk,
        "frequency_rank": rank,
        "frequency_badge": frequency_badge(rank),
        "status": word.status,
        "sentence_count": sentence_count,
        "created_at": word.created_at,
        "updated_at": word.updated_at,
    }


def _unknown_word_dict(word: str, persistence: Persistence) -> dict:
    """Build a vocab dict for a word not yet in the vocab table."""
    from langmine.language_factory import get_proficiency_level as get_hsk_level
    from langmine.domain.models import frequency_badge

    sentences = persistence.get_sentences_by_word(word)
    hsk = get_hsk_level(word)

    return {
        "word": word,
        "reading": "",
        "definition_de": "",
        "definition_en": "",
        "hsk_level": hsk,
        "frequency_rank": None,
        "frequency_badge": "",
        "status": "unknown",
        "sentence_count": len(sentences),
    }


def _cascade_word_known(
    persistence: Persistence, word: str,
    processor: LanguageProcessor | None = None,
) -> None:
    """Reclassify all sentences where `word` is the unknown_word.

    - i+1 sentences → i0 (word is now known)
    - Stashed sentences get rechecked via SentenceClassifier per affected video
    """
    sentences = persistence.get_sentences_by_word(word)
    affected_videos: set[int] = set()

    for s in sentences:
        if s.unknown_word == word and s.status == "i1":
            s.status = "i0"
            persistence.update_sentence(s)
            persistence.log_event(
                entity_type="sentence", entity_id=s.id or 0,
                action="i0", old_value="i1", new_value="i0",
                language_code=s.language_code,
            )
            affected_videos.add(s.video_id)

    # Re-run classifier on stashed sentences for affected videos
    if processor and affected_videos:
        from langmine.domain.classifier import SentenceClassifier
        classifier = SentenceClassifier(processor, persistence)
        for vid in affected_videos:
            promoted = classifier.reclassify_stashed(vid)
            # Log events for promoted sentences
            if promoted:
                stashed = persistence.get_sentences_by_video(
                    vid, status="i1"
                )
                for s in stashed:
                    persistence.log_event(
                        entity_type="sentence", entity_id=s.id or 0,
                        action="classified_i1", old_value="stashed",
                        new_value="i1",
                        language_code=s.language_code,
                    )
    elif affected_videos:
        for vid in affected_videos:
            persistence.reclassify_stashed(vid)
