"""Sentence management API routes."""

import json
import os

from flask import Blueprint, current_app, jsonify, request, send_file

from ._helpers import (
    EDITABLE_FIELDS,
    VALID_SENTENCE_STATUSES,
    _find_sentence,
    _get_audio_processor,
    _get_classifier,
    _get_language_code,
    _get_persistence,
    _get_processor,
    _get_sentence_or_404,
    _reclassify_from_segmented,
    _sentence_to_dict,
)

sentences_bp = Blueprint("sentences", __name__)


@sentences_bp.route("/api/sentences/<int:sentence_id>", methods=["PATCH"])
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
            return jsonify(
                {
                    "error": f"Invalid status '{status}'. Must be one of: {sorted(VALID_SENTENCE_STATUSES)}"
                }
            ), 400
        sentence.status = status
        # If keeping, mark unknown word as "learning"
        if status == "kept" and sentence.unknown_word:
            persistence.mark_word_learning(sentence.unknown_word)

        # Log the status change event
        persistence.log_event(
            entity_type="sentence",
            entity_id=sentence.id,
            action=status,
            old_value=old_status,
            new_value=status,
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
            entity_type="sentence",
            entity_id=sentence.id,
            action="edited",
            new_value=",".join(f for f in EDITABLE_FIELDS if f in data),
            language_code=sentence.language_code,
        )

    return jsonify(
        {
            "sentence": _sentence_to_dict(
                sentence, persistence, processor=_get_processor()
            ),
        }
    )


@sentences_bp.route(
    "/api/sentences/<int:sentence_id>/merge-with-previous", methods=["POST"]
)
def merge_with_previous(sentence_id: int):
    """Merge sentence B into the previous sentence A (M24).

    Concatenates text, text_segmented, reading, translation_de.
    Re-enriches NLP fields. Re-generates audio clip for merged span.
    Marks sentence B as deleted.
    """
    persistence = _get_persistence()
    lang = _get_language_code()

    sentence_b = _get_sentence_or_404(persistence, sentence_id)

    # Find the previous non-deleted sentence (A) — same video, earlier start_ms
    all_sentences = persistence.get_sentences_by_video(
        sentence_b.video_id, language_code=lang
    )
    # Exclude deleted sentences from predecessor search
    active = sorted(
        [s for s in all_sentences if s.status != "deleted"],
        key=lambda s: s.start_ms,
    )
    b_idx = None
    for i, s in enumerate(active):
        if s.id == sentence_b.id:
            b_idx = i
            break
    if b_idx is None or b_idx == 0:
        return jsonify({"error": "No previous sentence to merge with"}), 400

    sentence_a = active[b_idx - 1]

    # Merge text fields
    sentence_a.text += " " + sentence_b.text
    sentence_a.text_segmented += " / " + sentence_b.text_segmented

    # Merge reading and translation (preserve even if A was empty)
    if sentence_b.reading:
        if sentence_a.reading:
            sentence_a.reading += " " + sentence_b.reading
        else:
            sentence_a.reading = sentence_b.reading
    if sentence_b.translation_de:
        if sentence_a.translation_de:
            sentence_a.translation_de += " " + sentence_b.translation_de
        else:
            sentence_a.translation_de = sentence_b.translation_de

    # Span timing
    sentence_a.end_ms = sentence_b.end_ms

    # Re-enrich NLP for the merged text (reading, translation, annotations)
    processor = _get_processor()
    if processor:
        classifier = _get_classifier()
        classifier.enrich([sentence_a])

    # Re-classify based on merged word segmentation
    _reclassify_from_segmented(persistence, sentence_a)

    # Regenerate audio clip for the merged span (best effort)
    audio = _get_audio_processor()
    if audio:
        import os
        from pathlib import Path

        config = current_app.config["LANGMINE_CONFIG"]
        videos = persistence.list_videos()
        video = next((v for v in videos if v.id == sentence_a.video_id), None)
        if video and video.audio_path:
            data_dir = str(Path(config.data_dir).expanduser())
            clip_dir = os.path.join(data_dir, "clips")
            os.makedirs(clip_dir, exist_ok=True)
            try:
                clip_path = audio.clip(
                    audio_path=video.audio_path,
                    start_ms=sentence_a.start_ms,
                    end_ms=sentence_a.end_ms,
                    pad_before_ms=config.audio_pad_before_ms,
                    pad_after_ms=config.audio_pad_after_ms,
                    output_dir=clip_dir,
                    sentence_id=str(sentence_a.id).zfill(4),
                )
                sentence_a.audio_clip_path = clip_path
            except Exception:
                pass  # best effort — audio clipping may not be available

    # Persist A first, then mark B as deleted (rollback-safe ordering)
    persistence.update_sentence(sentence_a)

    sentence_b.status = "deleted"
    persistence.update_sentence(sentence_b)

    persistence.log_event(
        entity_type="sentence",
        entity_id=sentence_a.id,
        action="merged",
        old_value=str(sentence_b.id),
        new_value=sentence_a.text_segmented,
        language_code=lang,
    )

    return jsonify(
        {
            "sentence": _sentence_to_dict(sentence_a, persistence, processor=processor),
            "merged_id": sentence_b.id,
            "ok": True,
        }
    )


@sentences_bp.route("/api/sentences/<int:sentence_id>/iknowthis", methods=["PATCH"])
def mark_word_known(sentence_id: int):
    """Mark the unknown word in this sentence as known.

    Also reclassifies the sentence to i0 if it was i1.
    """
    persistence = _get_persistence()
    _get_processor()

    sentence = _find_sentence(persistence, sentence_id)
    if sentence is None:
        return jsonify({"error": "Sentence not found"}), 404

    if sentence.unknown_word is None:
        return jsonify({"error": "Sentence has no unknown word to mark as known"}), 400

    word = sentence.unknown_word
    persistence.mark_word_known(word)

    persistence.log_event(
        entity_type="word",
        entity_id=sentence.id,
        action="marked_known",
        new_value=word,
        language_code=sentence.language_code,
    )

    # Re-classify: with the word now known, this sentence should be i0
    sentence.status = "i0"
    persistence.update_sentence(sentence)

    return jsonify(
        {
            "word_marked": word,
            "sentence": _sentence_to_dict(
                sentence, persistence, processor=_get_processor()
            ),
        }
    )


@sentences_bp.route("/api/sentences/<int:sentence_id>/audio")
def serve_audio(sentence_id: int):
    """Serve the audio clip for a sentence."""
    persistence = _get_persistence()
    sentence = _find_sentence(persistence, sentence_id)
    if sentence is None:
        return jsonify({"error": "Sentence not found"}), 404

    if not sentence.audio_clip_path or not os.path.exists(
        os.path.expanduser(sentence.audio_clip_path)
    ):
        return jsonify({"error": "Audio file not found"}), 404

    return send_file(
        os.path.expanduser(sentence.audio_clip_path),
        mimetype="audio/mpeg",
        as_attachment=False,
    )


@sentences_bp.route("/api/sentences/<int:sentence_id>/screenshot")
def serve_screenshot(sentence_id: int):
    """Serve the screenshot for a sentence."""
    persistence = _get_persistence()
    sentence = _find_sentence(persistence, sentence_id)
    if sentence is None:
        return jsonify({"error": "Sentence not found"}), 404

    if not sentence.screenshot_path or not os.path.exists(
        os.path.expanduser(sentence.screenshot_path)
    ):
        return jsonify({"error": "Screenshot not found"}), 404

    return send_file(
        os.path.expanduser(sentence.screenshot_path),
        mimetype="image/jpeg",
        as_attachment=False,
    )


# === Image Search API (M12) ===


@sentences_bp.route("/api/sentences/<int:sentence_id>/cloze-image", methods=["POST"])
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

    return jsonify(
        {
            "ok": True,
            "sentence_id": sentence_id,
            "cloze_image_url": sentence.cloze_image_url,
        }
    )


@sentences_bp.route("/api/sentences/<int:sentence_id>/annotation", methods=["PATCH"])
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
        return jsonify(
            {
                "error": f"Index {index} out of range (0-{len(annotation) - 1 if annotation else -1})"
            }
        ), 400

    entry = annotation[index]
    for field in ("char", "pinyin", "tone", "definition"):
        if field in data:
            entry[field] = data[field]

    sentence.annotation_json = json.dumps(annotation)
    persistence.update_sentence(sentence)

    persistence.log_event(
        entity_type="sentence",
        entity_id=sentence.id,
        action="annotation_edited",
        new_value=str(index),
        language_code=sentence.language_code,
    )

    return jsonify({"ok": True, "annotation": annotation})


# === Vocab API ===
