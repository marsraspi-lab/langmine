"""Anki export API routes."""

from flask import Blueprint, current_app, jsonify, request

from ._helpers import (
    _get_language_code,
    _get_persistence,
)

export_bp = Blueprint("export", __name__)


@export_bp.route("/api/export/anki", methods=["POST"])
def export_anki():
    """Export kept sentences directly to Anki via AnkiConnect."""
    persistence = _get_persistence()
    exporter = current_app.config.get("LANGMINE_ANKI_EXPORTER")
    if exporter is None:
        return jsonify({"error": "Anki exporter not configured."}), 503

    data = request.get_json(silent=True) or {}
    video_id = data.get("video_id")
    all_kept = data.get("all_kept", False)
    force_update = data.get("force_update_model", False)
    card_type = data.get("card_type", "basic")

    sentences = _resolve_export_sentences(persistence, video_id, all_kept)
    if sentences is None:
        return jsonify({"error": "Specify video_id or all_kept=true"}), 400
    if not sentences:
        return jsonify({"error": "No kept sentences to export"}), 400

    try:
        result = _do_anki_export(exporter, persistence, sentences, card_type, force_update)
        return jsonify(result)
    except ConnectionError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"Export failed: {e}"}), 500


def _resolve_export_sentences(persistence, video_id, all_kept):
    """Resolve which sentences to export. Returns None if neither param set."""
    if video_id is not None:
        return persistence.get_sentences_by_video(video_id, status="kept")
    if all_kept:
        return persistence.get_sentences_by_status("kept")
    return None


def _do_anki_export(exporter, persistence, sentences, card_type, force_update):
    """Execute the Anki export and mark sentences as exported."""
    from langmine.language_factory import get_anki_templates, get_language_manifest

    lang = _get_language_code()
    manifest = get_language_manifest(lang)
    templates = get_anki_templates(lang)

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

    for s in sentences:
        s.status = "exported"
        persistence.update_sentence(s)
        persistence.log_event(
            entity_type="sentence",
            entity_id=s.id or 0,
            action="exported",
            old_value="kept",
            new_value="exported",
            language_code=lang,
        )

    return result
