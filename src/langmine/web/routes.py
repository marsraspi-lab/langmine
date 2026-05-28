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
        """Mine a YouTube video: transcript → merge → classify → persist."""
        persistence = _get_persistence()
        processor = _get_processor()
        transcript = _get_transcript_source()
        audio = _get_audio_processor()

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
            output_dir = getattr(config, "data_dir", "/tmp/langmine")
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
            "sentences": [_sentence_to_dict(s) for s in sentences],
        })

    @app.route("/api/sentences/<int:sentence_id>", methods=["PATCH"])
    def update_sentence(sentence_id: int):
        """Update sentence status (kept/deleted)."""
        persistence = _get_persistence()

        data = request.get_json(silent=True)
        if not data or "status" not in data:
            return jsonify({"error": "Missing 'status' field"}), 400

        status = data["status"]
        if status not in VALID_SENTENCE_STATUSES:
            return jsonify({
                "error": f"Invalid status '{status}'. Must be one of: {sorted(VALID_SENTENCE_STATUSES)}"
            }), 400

        sentence = _find_sentence(persistence, sentence_id)
        if sentence is None:
            return jsonify({"error": "Sentence not found"}), 404

        sentence.status = status
        persistence.update_sentence(sentence)

        # If keeping, mark unknown word as "learning"
        if status == "kept" and sentence.unknown_word:
            persistence.mark_word_learning(sentence.unknown_word)

        return jsonify({
            "sentence": _sentence_to_dict(sentence),
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
            "sentence": _sentence_to_dict(sentence),
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

    @app.route("/api/stats")
    def stats():
        """Return vocabulary stats."""
        persistence = _get_persistence()
        return jsonify(persistence.get_vocab_stats())


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


def _sentence_to_dict(sentence: Sentence) -> dict:
    """Convert a Sentence domain model to a JSON-safe dict."""
    from langmine.adapters.subtlex_ch import SubtlexChAdapter

    result = {
        "id": sentence.id,
        "video_id": sentence.video_id,
        "text": sentence.text,
        "text_segmented": sentence.text_segmented,
        "pinyin": sentence.pinyin,
        "translation_de": sentence.translation_de,
        "unknown_word": sentence.unknown_word,
        "unknown_word_rank": sentence.unknown_word_rank,
        "status": sentence.status,
        "has_audio": bool(sentence.audio_clip_path),
    }

    # Compute frequency badge from rank
    result["frequency_badge"] = SubtlexChAdapter.get_badge(sentence.unknown_word_rank)

    return result
